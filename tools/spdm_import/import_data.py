#!/usr/bin/env python3
"""Import an existing matched 23-column CSV and analysis JSON into an empty DB.

No synthetic data or incremental synchronization is performed. Row identifiers
count CSV records with the header as record 1; embedded cell newlines do not
increment this identifier. Both external identifiers must agree when present.
"""

import argparse
from collections import Counter
from contextlib import closing
import csv
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

from db_common import SCHEMA_PATH, connect_database, distinct_paths, ensure_empty, validate_schema

EXPECTED_HEADERS = [
    'adminno', 'seqno', 'sec_code', 'writer', 'comp_date', 'maker', 'maker_pn',
    'adminno', 'seqno', 'Checkpoint', 'Specification', '설계치', '참조문서',
    'input_5', 'savefolder', 'ref_date', 'category', 'pin_info',
    'ldrc_check_tp', 'ldrc_regist_tp', 'ldrc_check_date', 'ldrc_checker', 'ldrc_id',
]
EVIDENCE_COLUMN = {'checkpoint': 9, 'specification': 10, 'design_template': 11, 'reference_document': 12}
ALLOWED_ARCHETYPES = {
    'power_rail', 'decap', 'pull_up_down', 'unused_pin',
    'power_sequencing', 'signal_integrity', 'other',
}
# S:W are checkpoint-specific LDRC metadata and must not be compared per part.
SHARED_PART_COLUMNS = (2, 3, 4, 5, 6)
OPTIONAL_SHARED_COLUMNS = frozenset((5, 6))
SHARED_DATE_COLUMNS = frozenset((4,))


def optional(value):
    return None if value is None or value == '' else value


def optional_shared_text(value):
    """A whitespace-only optional source cell denotes missing information."""
    return None if value is None or not value.strip() else value


def normalized_shared_value(column, value):
    """Compare missing values and equal serial dates without altering raw CSV."""
    if column in OPTIONAL_SHARED_COLUMNS and optional_shared_text(value) is None:
        return None
    if column in SHARED_DATE_COLUMNS:
        try:
            numeric = Decimal(value)
            if numeric.is_finite():
                return numeric
        except InvalidOperation:
            pass
    # Identifiers and nonempty text remain exact, including case and spaces.
    return value


def describe_shared_difference(column, previous, current):
    def display(value):
        text = repr(value)
        return text if len(text) <= 160 else text[:157] + '...'

    letter = chr(ord('A') + column)
    return (f'{letter}열 {EXPECTED_HEADERS[column]}: '
            f'이전={display(previous)} / 현재={display(current)}')


def shared_part_error(first_row_no, row_no, differences):
    return ('Inconsistent shared fields for part\n'
            f'비교 레코드: 최초 {first_row_no}번 / 현재 {row_no}번 (헤더=1)\n'
            '다른 컬럼:\n' + '\n'.join(differences))


def encode_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def require_type(value, expected, path):
    if not isinstance(value, expected):
        raise ValueError(f'{path}: {expected.__name__} 타입이 필요합니다.')
    return value


def reject_constant(value):
    raise ValueError(f'비유한 JSON 숫자는 허용하지 않습니다: {value}')


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'중복 JSON 객체 키: {key}')
        result[key] = value
    return result


def load_analysis(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8-sig'),
                         object_pairs_hook=unique_keys, parse_constant=reject_constant)
    require_type(payload, list, '/')
    # Also catches overflow such as JSON number 1e999, without changing its type.
    encode_json(payload)
    return payload


def parse_parameter(value):
    """Preserve strings and JSON structures; derive finite numeric/range fields."""
    if value is None:
        return None, None, None, None
    if isinstance(value, bool):
        raise ValueError('A parameter value cannot be Boolean')
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError('Parameter number must be finite')
        return encode_json(value), numeric, None, None
    if isinstance(value, (list, dict)):
        return encode_json(value), None, None, None
    require_type(value, str, 'parameter.value')
    raw = value
    number = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
    match = re.fullmatch(rf'({number})\s*(?:~|to|–|-)\s*({number})', raw.strip(), flags=re.IGNORECASE)
    if match:
        lower, upper = map(float, match.groups())
        if not all(map(math.isfinite, (lower, upper))) or lower > upper:
            raise ValueError('Invalid parameter range')
        return raw, None, lower, upper
    try:
        numeric = float(raw)
    except ValueError:
        return raw, None, None, None
    if not math.isfinite(numeric):
        raise ValueError('Parameter number must be finite')
    return raw, numeric, None, None


def read_csv(path):
    with Path(path).open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        if next(reader, None) != EXPECTED_HEADERS:
            raise ValueError('CSV must contain the expected 23 columns in the original order')
        for row_no, row in enumerate(reader, start=2):
            if len(row) != 23:
                raise ValueError(f'CSV row {row_no} has {len(row)} columns, expected 23')
            if row[0] != row[7]:
                raise ValueError(f'CSV row {row_no}: adminno mismatch')
            yield row_no, row


def import_csv(conn, path):
    path = Path(path)
    parts_by_key, fields_by_key, checkpoints_by_row = {}, {}, {}
    for row_no, row in read_csv(path):
        try:
            part_seq, check_seq = int(row[1]), int(row[8])
            if not row[2].strip():
                raise ValueError('sec_code must be nonempty')
            part_key = (row[0], part_seq)
            common = tuple(row[column] for column in SHARED_PART_COLUMNS)
            if part_key in fields_by_key:
                first_row_no, first_common = fields_by_key[part_key]
                differences = [
                    describe_shared_difference(column, previous, current)
                    for column, previous, current in zip(SHARED_PART_COLUMNS, first_common, common)
                    if normalized_shared_value(column, previous) != normalized_shared_value(column, current)
                ]
                if differences:
                    raise ValueError(shared_part_error(first_row_no, row_no, differences))
            else:
                fields_by_key[part_key] = (row_no, common)
            if part_key not in parts_by_key:
                cursor = conn.execute('''
                    INSERT INTO parts (
                        adminno, part_seqno, sec_code, writer_emp_no, comp_date_serial,
                        maker, maker_pn
                    ) VALUES (?,?,?,?,?,?,?)
                ''', (row[0], part_seq, row[2], row[3], row[4], optional_shared_text(row[5]),
                      optional_shared_text(row[6])))
                parts_by_key[part_key] = cursor.lastrowid
            cursor = conn.execute('''
                INSERT INTO checkpoints (
                    part_id, checkpoint_seqno, checkpoint_text, specification_text,
                    design_template_text, reference_document, input_emp_no, savefolder,
                    ref_date_serial, category, pin_info,
                    ldrc_check_tp, ldrc_regist_tp, ldrc_check_date_serial,
                    ldrc_checker_emp_no, ldrc_id, external_checkpoint_id,
                    source_row_uid, source_file_name, source_row_no, raw_row_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (parts_by_key[part_key], check_seq, optional(row[9]), optional(row[10]), optional(row[11]),
                  optional(row[12]), row[13], row[14], row[15], optional(row[16]), optional(row[17]),
                  *[optional_shared_text(value) for value in row[18:23]],
                  f'row:{row_no}', f'csv:{path.name}:{row_no}', path.name, row_no, encode_json(row)))
            checkpoints_by_row[row_no] = (cursor.lastrowid, row)
        except (ValueError, OverflowError, sqlite3.IntegrityError) as error:
            raise ValueError(f'CSV row {row_no}: {error}') from error
    return parts_by_key, checkpoints_by_row


def source_row_number(item):
    require_type(item, dict, 'analysis record')
    checkpoint_id = item.get('checkpoint_id')
    row_uid = item.get('row_uid')
    found = []
    if isinstance(checkpoint_id, str) and re.fullmatch(r'row:[0-9]+', checkpoint_id):
        found.append(int(checkpoint_id.split(':')[1]))
    if isinstance(row_uid, str) and re.search(r':[0-9]+$', row_uid):
        found.append(int(row_uid.rsplit(':', 1)[-1]))
    if not found or found[0] < 2 or any(value != found[0] for value in found):
        raise ValueError('checkpoint_id/row_uid must identify the same CSV data row (>=2)')
    return found[0]


def import_analysis(conn, path, checkpoints_by_row):
    payload = load_analysis(path)
    processed_rows, counts = set(), Counter()
    for index, item in enumerate(payload):
        try:
            row_no = source_row_number(item)
            if row_no in processed_rows:
                raise ValueError(f'Duplicate analysis entry for source row {row_no}')
            processed_rows.add(row_no)
            if row_no not in checkpoints_by_row:
                raise ValueError(f'Analysis references unknown CSV row {row_no}')
            checkpoint_id, source_row = checkpoints_by_row[row_no]
            if item.get('sec_code') != source_row[2]:
                raise ValueError(f'sec_code mismatch for CSV row {row_no}')
            for key in ('checkpoint_id', 'row_uid', 'status'):
                require_type(item[key], str, f'/{index}/{key}')
            analysis = item['analysis']
            if analysis is not None:
                require_type(analysis, dict, f'/{index}/analysis')
                require_type(analysis['summary'], str, f'/{index}/analysis/summary')
                require_type(analysis['checks'], list, f'/{index}/analysis/checks')
                require_type(analysis['issues'], list, f'/{index}/analysis/issues')
            conn.execute('UPDATE checkpoints SET external_checkpoint_id=?, source_row_uid=? WHERE checkpoint_id=?',
                         (item['checkpoint_id'], item['row_uid'], checkpoint_id))
            cursor = conn.execute('''
                INSERT INTO checkpoint_analyses (checkpoint_id, version_no, summary, status, raw_analysis_json)
                VALUES (?, 1, ?, ?, ?)
            ''', (checkpoint_id, optional(analysis['summary']) if analysis is not None else None,
                  item['status'], encode_json(item)))
            analysis_id = cursor.lastrowid
            counts['analyses'] += 1
            if analysis is None:
                continue
            for check_no, check in enumerate(analysis['checks'], start=1):
                require_type(check, dict, f'/{index}/analysis/checks/{check_no - 1}')
                if check.get('sec_code') != source_row[2]:
                    raise ValueError(f'Check sec_code mismatch for CSV row {row_no}')
                for key in ('requirement_id', 'target_kind', 'target_description', 'requirement', 'level'):
                    require_type(check[key], str, f'check.{key}')
                applicability = check.get('applicability')
                if applicability is not None:
                    require_type(applicability, str, 'check.applicability')
                archetype = check.get('archetype')
                if archetype is None or archetype == '':
                    archetype = 'other'
                require_type(archetype, str, 'check.archetype')
                if archetype not in ALLOWED_ARCHETYPES:
                    raise ValueError('Unknown archetype')
                cursor = conn.execute('''
                    INSERT INTO analysis_checks (
                        analysis_id, requirement_id, rule_seq, target_kind, target_description,
                        applicability, requirement_text, level, archetype
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                ''', (analysis_id, check['requirement_id'], check_no, check['target_kind'],
                      check['target_description'], optional(applicability), check['requirement'], check['level'], archetype))
                check_id = cursor.lastrowid
                counts['checks'] += 1
                for field in ('parameters', 'required_design_facts', 'evidence'):
                    require_type(check[field], list, f'check.{field}')
                for param_no, param in enumerate(check['parameters'], start=1):
                    require_type(param, dict, 'parameter')
                    for key in ('name', 'role'):
                        require_type(param[key], str, f'parameter.{key}')
                    for key in ('unit', 'qualifier'):
                        if param.get(key) is not None:
                            require_type(param[key], str, f'parameter.{key}')
                    raw, numeric, lower, upper = parse_parameter(param['value'])
                    conn.execute('''
                        INSERT INTO check_parameters (
                            analysis_check_id, param_seq, param_name, value_text, numeric_value,
                            min_value, max_value, unit, role, qualifier
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    ''', (check_id, param_no, param['name'], raw, numeric, lower, upper,
                          optional(param.get('unit')), param['role'], optional(param.get('qualifier'))))
                    counts['parameters'] += 1
                for fact_no, fact in enumerate(check['required_design_facts'], start=1):
                    require_type(fact, str, 'required_design_facts item')
                    conn.execute('INSERT INTO check_required_facts (analysis_check_id, fact_seq, fact_name) VALUES (?,?,?)',
                                 (check_id, fact_no, fact))
                    counts['facts'] += 1
                for evidence_no, evidence in enumerate(check['evidence'], start=1):
                    require_type(evidence, dict, 'evidence')
                    evidence_field, quote = evidence['field'], evidence['quote']
                    require_type(evidence_field, str, 'evidence.field')
                    require_type(quote, str, 'evidence.quote')
                    if evidence_field not in EVIDENCE_COLUMN:
                        raise ValueError('Unknown evidence field')
                    if not quote or quote not in source_row[EVIDENCE_COLUMN[evidence_field]]:
                        raise ValueError(f'Evidence mismatch for CSV row {row_no}, field {evidence_field}')
                    conn.execute('INSERT INTO check_evidence (analysis_check_id, evidence_seq, source_field, quote_text) VALUES (?,?,?,?)',
                                 (check_id, evidence_no, evidence_field, quote))
                    counts['evidence'] += 1
            for issue_no, issue in enumerate(analysis['issues'], start=1):
                require_type(issue, dict, 'issue')
                for key in ('code', 'description'):
                    require_type(issue[key], str, f'issue.{key}')
                conn.execute('INSERT INTO analysis_issues (analysis_id, issue_seq, code, description) VALUES (?,?,?,?)',
                             (analysis_id, issue_no, issue['code'], issue['description']))
                counts['issues'] += 1
        except (KeyError, TypeError, ValueError, OverflowError, sqlite3.IntegrityError) as error:
            raise ValueError(f'JSON /{index}: {error}') from error
    if processed_rows != set(checkpoints_by_row):
        raise ValueError(f'Analysis JSON missing {len(set(checkpoints_by_row) - processed_rows)} CSV rows')
    return counts


def import_files(database, csv_path, analysis_path):
    database, csv_path, analysis_path = map(Path, (database, csv_path, analysis_path))
    distinct_paths(database, csv_path, analysis_path, SCHEMA_PATH)
    if not csv_path.is_file() or not analysis_path.is_file():
        raise ValueError('기존 실제 CSV와 분석 JSON 파일을 모두 지정하세요.')
    with closing(connect_database(database)) as connection:
        connection.execute('BEGIN IMMEDIATE')
        try:
            validate_schema(connection)
            ensure_empty(connection)
            parts, checkpoints = import_csv(connection, csv_path)
            counts = import_analysis(connection, analysis_path, checkpoints)
            if connection.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Foreign-key violations')
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return {'status': 'imported', 'database': str(database.resolve()), 'parts': len(parts),
            'checkpoints': len(checkpoints), **{key: counts[key] for key in
            ('analyses', 'checks', 'parameters', 'facts', 'evidence', 'issues')}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--analysis', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = import_files(args.db, args.csv, args.analysis)
        print(f"Imported {result['parts']} parts, {result['checkpoints']} checkpoints, {result['checks']} analysis checks.")
        print(f"Parameters: {result['parameters']}, facts: {result['facts']}, evidence: {result['evidence']}, issues: {result['issues']}.")
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error, csv.Error, RecursionError) as error:
        print(f'적재 오류(이번 가져오기 전체 취소): {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
