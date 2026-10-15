"""JSON rule snapshots. Circuit facts and verdicts are separate data."""

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3


APPLICATION_ID = 0x5350444D
SCHEMA_VERSION = 3
IMPORTER_VERSION = "json-only:1"
SEC_CHECK = """((length(sec_code)=8 AND sec_code NOT GLOB '*[^0-9]*') OR
    (length(sec_code)=11 AND substr(sec_code,5,1)='-' AND
     substr(sec_code,1,4) NOT GLOB '*[^0-9]*' AND substr(sec_code,6,6) NOT GLOB '*[^0-9]*'))"""
SCHEMA = [
    """CREATE TABLE import_batches (
        id INTEGER PRIMARY KEY,
        source_file TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        contract_sha256 TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        importer_version TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        checkpoint_count INTEGER NOT NULL,
        rule_count INTEGER NOT NULL,
        contract_json TEXT NOT NULL,
        inspection_json TEXT NOT NULL,
        UNIQUE(source_sha256, contract_sha256, parser_version, importer_version)
    )""",
    f"""CREATE TABLE checkpoints (
        id INTEGER PRIMARY KEY,
        batch_id INTEGER NOT NULL REFERENCES import_batches(id),
        source_record_index INTEGER NOT NULL,
        checkpoint_id TEXT NOT NULL,
        row_uid TEXT NOT NULL,
        sec_code TEXT NOT NULL CHECK {SEC_CHECK},
        status TEXT NOT NULL,
        summary TEXT,
        issues_json TEXT NOT NULL,
        raw_json TEXT NOT NULL,
        UNIQUE(batch_id, source_record_index),
        UNIQUE(id, batch_id)
    )""",
    f"""CREATE TABLE rules (
        id INTEGER PRIMARY KEY,
        batch_id INTEGER NOT NULL REFERENCES import_batches(id),
        checkpoint_db_id INTEGER NOT NULL,
        source_row INTEGER NOT NULL,
        source_check_index INTEGER NOT NULL,
        requirement_id TEXT NOT NULL,
        sec_code TEXT NOT NULL CHECK {SEC_CHECK},
        specification TEXT NOT NULL,
        target_kind TEXT NOT NULL,
        target_description TEXT NOT NULL,
        applicability TEXT NOT NULL,
        level TEXT NOT NULL,
        parameters_json TEXT NOT NULL,
        required_design_facts_json TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        raw_json TEXT NOT NULL,
        issues_json TEXT NOT NULL,
        duplicate_first_row INTEGER,
        FOREIGN KEY(checkpoint_db_id, batch_id) REFERENCES checkpoints(id, batch_id),
        UNIQUE(batch_id, source_row),
        UNIQUE(checkpoint_db_id, source_check_index)
    )""",
    "CREATE INDEX rules_batch_sec ON rules(batch_id, sec_code)",
]


class InspectionError(ValueError):
    def __init__(self, report):
        super().__init__(f"JSON 오류 {report['errors']}건: 이번 가져오기를 전부 취소함")
        self.report = report


def encode_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def validate_sec_code(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9]{8}|[0-9]{4}-[0-9]{6})", value.strip()):
        raise ValueError("SEC는 8자리 또는 4자리-6자리 원본 문자열이어야 함; 임의 변환하지 않음")
    return value.strip()


def distinct_paths(*paths):
    paths = [Path(path) for path in paths if path is not None]
    for i, left in enumerate(paths):
        for right in paths[i + 1:]:
            if left.resolve() == right.resolve() or (
                left.exists() and right.exists() and left.samefile(right)
            ):
                raise ValueError("입력·계약·DB·보고서 파일 경로는 서로 달라야 함")


def check_schema(connection):
    if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
        raise ValueError("이 도구의 SPDM JSON DB가 아님")
    if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        raise ValueError("지원하지 않는 DB 버전; 기존 DB를 보존하고 새 JSON DB 경로를 사용하세요")


def initialize_schema(connection):
    application_id = connection.execute("PRAGMA application_id").fetchone()[0]
    objects = connection.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    if application_id == 0 and not objects and connection.execute("PRAGMA user_version").fetchone()[0] == 0:
        for statement in SCHEMA:
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    else:
        check_schema(connection)


def import_analysis(source, database, preview_limit=10):
    from json_rules import JSON_PARSER_VERSION, load_contract, parse_analysis

    source, database = Path(source), Path(database)
    distinct_paths(source, database)
    source_bytes = source.read_bytes()
    parsed = parse_analysis(source, preview_limit, source_bytes=source_bytes)
    report = parsed.report
    if report["errors"]:
        raise InspectionError(report)
    identity = (hashlib.sha256(source_bytes).hexdigest(), report["contract_sha256"],
                JSON_PARSER_VERSION, IMPORTER_VERSION)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            initialize_schema(connection)
            existing = connection.execute(
                "SELECT id, rule_count FROM import_batches WHERE source_sha256=? AND contract_sha256=? "
                "AND parser_version=? AND importer_version=?", identity).fetchone()
            if existing:
                connection.rollback()
                return {"status": "skipped", "batch_id": existing[0], "stored_rows": existing[1], "inspection": report}
            batch_id = connection.execute(
                "INSERT INTO import_batches(source_file, source_sha256, contract_sha256, parser_version, "
                "importer_version, imported_at, checkpoint_count, rule_count, contract_json, inspection_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (source.name, *identity, datetime.now(timezone.utc).isoformat(), len(parsed.records),
                 len(parsed.rows), encode_json(load_contract()), encode_json(report))
            ).lastrowid
            checkpoint_ids = {}
            for index, record in enumerate(parsed.records):
                analysis = record["analysis"]
                checkpoint_ids[index] = connection.execute(
                    "INSERT INTO checkpoints(batch_id, source_record_index, checkpoint_id, row_uid, sec_code, "
                    "status, summary, issues_json, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (batch_id, index, record["checkpoint_id"], record["row_uid"], record["sec_code"], record["status"],
                     analysis["summary"] if analysis else None,
                     encode_json(analysis["issues"] if analysis else []), encode_json(record))
                ).lastrowid
            for row in parsed.rows:
                check = row["raw"]
                connection.execute(
                    "INSERT INTO rules(batch_id, checkpoint_db_id, source_row, source_check_index, requirement_id, "
                    "sec_code, specification, target_kind, target_description, applicability, level, parameters_json, "
                    "required_design_facts_json, evidence_json, raw_json, issues_json, duplicate_first_row) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (batch_id, checkpoint_ids[row["record_index"]], row["source_row"], row["check_index"],
                     check["requirement_id"], check["sec_code"], check["requirement"],
                     check["target_kind"], check["target_description"], check["applicability"], check["level"],
                     *(encode_json(check[name]) for name in ("parameters", "required_design_facts", "evidence")),
                     encode_json(check), encode_json(row["issues"]), row["duplicate_first_row"]),
                )
            connection.commit()
            return {"status": "imported", "batch_id": batch_id, "stored_rows": len(parsed.rows), "inspection": report}
        except BaseException:
            connection.rollback()
            raise


def lookup_rules(database, sec_code, batch_id):
    """Read one explicit rule snapshot. A miss is never a PASS verdict."""
    sec_code = validate_sec_code(sec_code)
    if isinstance(batch_id, bool) or not isinstance(batch_id, int) or batch_id <= 0:
        raise ValueError("batch_id는 양의 정수여야 함")
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        check_schema(connection)
        batch = connection.execute("SELECT * FROM import_batches WHERE id=?", (batch_id,)).fetchone()
        if batch is None:
            raise ValueError(f"가져오기 batch_id={batch_id}가 없음")
        rows = connection.execute(
            "SELECT r.*, c.summary, c.checkpoint_id, c.row_uid, c.source_record_index, "
            "c.status AS checkpoint_status, c.issues_json AS checkpoint_issues_json "
            "FROM rules r JOIN checkpoints c ON c.id=r.checkpoint_db_id AND c.batch_id=r.batch_id "
            "WHERE r.batch_id=? AND r.sec_code=? ORDER BY r.source_row", (batch_id, sec_code)).fetchall()
        checkpoints = [dict(item) for item in connection.execute(
            "SELECT id, source_record_index, checkpoint_id, row_uid, sec_code, status, summary, "
            "issues_json FROM checkpoints WHERE batch_id=? AND sec_code=? ORDER BY source_record_index",
            (batch_id, sec_code))]
        for checkpoint in checkpoints:
            checkpoint["issues"] = json.loads(checkpoint.pop("issues_json"))
            checkpoint["original_checkpoint"] = None
        results = []
        for row in rows:
            item = dict(row)
            for name in ("raw", "issues", "parameters", "required_design_facts", "evidence", "checkpoint_issues"):
                item[name] = json.loads(item.pop(name + "_json"))
            item["source_json_pointer"] = f"/{item['source_record_index']}/analysis/checks/{item['source_check_index']}"
            item.update(requirement=item["specification"], checkpoint=item["summary"],
                        original_checkpoint=None, design_value=None)
            item["selected"] = {**item["raw"], "summary": item["summary"], "checkpoint": item["summary"],
                                "specification": item["specification"], "design_value": None,
                                "original_checkpoint": None}
            item["display_fields"] = {"checkPoint": item["summary"], "checkPoint_source": "analysis.summary",
                                      "original_checkPoint": None, "specification": item["specification"],
                                      "설계치": item["required_design_facts"], "설계치_kind": "required_design_facts"}
            item["has_preprocessing_issues"] = bool(item["issues"] or item["checkpoint_issues"])
            results.append(item)
        return {"batch_id": batch_id, "sec_code": sec_code, "source_file": batch["source_file"],
                "source_sha256": batch["source_sha256"], "contract_sha256": batch["contract_sha256"],
                "source_format": "json", "match_status": "MATCHED" if results else "NO_CHECKS" if checkpoints else "NOT_FOUND",
                "checkpoints": checkpoints, "rules": results}
