"""Latest JSON rules only. Circuit facts and verdicts are separate data."""

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3


APPLICATION_ID = 0x5350444D
SCHEMA_VERSION = 4
SEC_CHECK = """((length(sec_code)=8 AND sec_code NOT GLOB '*[^0-9]*') OR
    (length(sec_code)=11 AND substr(sec_code,5,1)='-' AND
     substr(sec_code,1,4) NOT GLOB '*[^0-9]*' AND substr(sec_code,6,6) NOT GLOB '*[^0-9]*'))"""
SCHEMA = [
    f"""CREATE TABLE checkpoints (
        id INTEGER PRIMARY KEY,
        source_record_index INTEGER NOT NULL,
        checkpoint_id TEXT NOT NULL,
        row_uid TEXT NOT NULL,
        sec_code TEXT NOT NULL CHECK {SEC_CHECK},
        status TEXT NOT NULL,
        summary TEXT,
        issues_json TEXT NOT NULL,
        raw_json TEXT NOT NULL,
        UNIQUE(source_record_index)
    )""",
    f"""CREATE TABLE rules (
        id INTEGER PRIMARY KEY,
        checkpoint_db_id INTEGER NOT NULL REFERENCES checkpoints(id),
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
        UNIQUE(source_row),
        UNIQUE(checkpoint_db_id, source_check_index)
    )""",
    "CREATE INDEX rules_sec ON rules(sec_code)",
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
    from json_rules import parse_analysis

    source, database = Path(source), Path(database)
    distinct_paths(source, database)
    source_bytes = source.read_bytes()
    parsed = parse_analysis(source, preview_limit, source_bytes=source_bytes)
    report = parsed.report
    if report["errors"]:
        raise InspectionError(report)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            initialize_schema(connection)
            had_content = connection.execute("SELECT EXISTS(SELECT 1 FROM checkpoints)").fetchone()[0]
            # Delete children first; both deletion and insertion are rolled back on failure.
            connection.execute("DELETE FROM rules")
            connection.execute("DELETE FROM checkpoints")
            checkpoint_ids = {}
            for index, record in enumerate(parsed.records):
                analysis = record["analysis"]
                checkpoint_ids[index] = connection.execute(
                    "INSERT INTO checkpoints(source_record_index, checkpoint_id, row_uid, sec_code, "
                    "status, summary, issues_json, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (index, record["checkpoint_id"], record["row_uid"], record["sec_code"], record["status"],
                     analysis["summary"] if analysis else None,
                     encode_json(analysis["issues"] if analysis else []), encode_json(record))
                ).lastrowid
            for row in parsed.rows:
                check = row["raw"]
                connection.execute(
                    "INSERT INTO rules(checkpoint_db_id, source_row, source_check_index, requirement_id, "
                    "sec_code, specification, target_kind, target_description, applicability, level, parameters_json, "
                    "required_design_facts_json, evidence_json, raw_json, issues_json, duplicate_first_row) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (checkpoint_ids[row["record_index"]], row["source_row"], row["check_index"],
                     check["requirement_id"], check["sec_code"], check["requirement"],
                     check["target_kind"], check["target_description"], check["applicability"], check["level"],
                     *(encode_json(check[name]) for name in ("parameters", "required_design_facts", "evidence")),
                     encode_json(check), encode_json(row["issues"]), row["duplicate_first_row"]),
                )
            connection.commit()
            return {"status": "replaced" if had_content else "imported",
                    "stored_checkpoints": len(parsed.records), "stored_rows": len(parsed.rows), "inspection": report}
        except BaseException:
            connection.rollback()
            raise


def lookup_rules(database, sec_code):
    """Read the current rules for one SEC. A miss is never a PASS verdict."""
    sec_code = validate_sec_code(sec_code)
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        check_schema(connection)
        rows = connection.execute(
            "SELECT r.*, c.summary, c.checkpoint_id, c.row_uid, c.source_record_index, "
            "c.status AS checkpoint_status, c.issues_json AS checkpoint_issues_json "
            "FROM rules r JOIN checkpoints c ON c.id=r.checkpoint_db_id "
            "WHERE r.sec_code=? ORDER BY r.source_row", (sec_code,)).fetchall()
        checkpoints = [dict(item) for item in connection.execute(
            "SELECT id, source_record_index, checkpoint_id, row_uid, sec_code, status, summary, "
            "issues_json FROM checkpoints WHERE sec_code=? ORDER BY source_record_index",
            (sec_code,))]
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
        return {"sec_code": sec_code,
                "source_format": "json", "match_status": "MATCHED" if results else "NO_CHECKS" if checkpoints else "NOT_FOUND",
                "checkpoints": checkpoints, "rules": results}
