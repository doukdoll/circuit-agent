"""Local rule snapshots. Board references and observed circuit facts belong to the caller."""

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3


APPLICATION_ID = 0x5350444D  # SPDM
SCHEMA_VERSION = 1
IMPORTER_VERSION = "1"
CORE_TYPES = {
    "part_adminno": "integer", "part_seqno": "integer", "sec_code": "sec_code",
    "maker": "text", "maker_pn": "text", "rule_adminno": "integer", "rule_seqno": "integer",
    "checkpoint": "text", "specification": "text", "design_value": "text",
    "reference_doc": "text", "category": "text", "pin_info": "text",
}
CORE_FIELDS = tuple(CORE_TYPES)
SCHEMA = [
    """CREATE TABLE import_batches (
        id INTEGER PRIMARY KEY,
        source_file TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        mapping_sha256 TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        importer_version TEXT NOT NULL,
        sheet_name TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        row_count INTEGER NOT NULL DEFAULT 0,
        mapping_json TEXT NOT NULL,
        inspection_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(source_sha256, mapping_sha256, parser_version, importer_version)
    )""",
    """CREATE TABLE rules (
        id INTEGER PRIMARY KEY,
        batch_id INTEGER NOT NULL REFERENCES import_batches(id),
        source_row INTEGER NOT NULL,
        part_adminno INTEGER,
        part_seqno INTEGER,
        sec_code TEXT NOT NULL CHECK(length(sec_code) = 8 AND sec_code NOT GLOB '*[^0-9]*'),
        maker TEXT,
        maker_pn TEXT,
        rule_adminno INTEGER,
        rule_seqno INTEGER,
        checkpoint TEXT,
        specification TEXT,
        design_value TEXT,
        reference_doc TEXT,
        category TEXT,
        pin_info TEXT,
        raw_json TEXT NOT NULL,
        selected_json TEXT NOT NULL,
        issues_json TEXT NOT NULL,
        duplicate_first_row INTEGER,
        UNIQUE(batch_id, source_row)
    )""",
    "CREATE INDEX rules_batch_sec ON rules(batch_id, sec_code)",
]


class InspectionError(ValueError):
    def __init__(self, report):
        super().__init__(f"변환 오류 {report['errors']}건: 이번 가져오기를 전부 취소함")
        self.report = report


def encode_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def distinct_paths(*paths):
    paths = [Path(path) for path in paths if path is not None]
    for i, left in enumerate(paths):
        for right in paths[i + 1:]:
            if left.resolve() == right.resolve() or (
                left.exists() and right.exists() and left.samefile(right)
            ):
                raise ValueError("입력·설정·DB·보고서 파일 경로는 서로 달라야 함")


def check_schema(connection):
    if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
        raise ValueError("이 도구의 SPDM DB가 아님")
    if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        raise ValueError("지원하지 않는 DB 스키마 버전")


def initialize_schema(connection):
    application_id = connection.execute("PRAGMA application_id").fetchone()[0]
    tables = connection.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    if application_id == 0 and not tables and connection.execute("PRAGMA user_version").fetchone()[0] == 0:
        # Individual statements keep DDL and data in the same transaction (executescript commits implicitly).
        for statement in SCHEMA:
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    else:
        check_schema(connection)


def import_workbook(source, database, config, preview_limit=10):
    from inspect_rules import PARSER_VERSION, inspect_workbook

    source, database = Path(source), Path(database)
    distinct_paths(source, database)
    field_map = {field["name"]: field for field in config["fields"]}
    if "sec_code" not in field_map or field_map["sec_code"]["type"] != "sec_code":
        raise ValueError("DB 적재에는 sec_code 필드와 sec_code 타입 매핑이 필요함")
    for name, field in field_map.items():
        if name in CORE_TYPES and field["type"] != CORE_TYPES[name]:
            raise ValueError(f"DB 기본 필드 {name}의 타입은 {CORE_TYPES[name]}이어야 함")
    if preview_limit < 0:
        raise ValueError("preview는 0 이상이어야 함")
    # Hash and parse the same bytes, even if the source file changes during the import.
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    mapping_json = encode_json(config)
    mapping_hash = hashlib.sha256(mapping_json.encode("utf-8")).hexdigest()
    identity = (source_hash, mapping_hash, PARSER_VERSION, IMPORTER_VERSION)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            initialize_schema(connection)
            existing = connection.execute(
                "SELECT id, row_count FROM import_batches WHERE "
                "source_sha256=? AND mapping_sha256=? AND parser_version=? AND importer_version=?", identity
            ).fetchone()
            if existing:
                report = inspect_workbook(source, config, preview_limit, source_bytes=source_bytes)
                connection.rollback()
                return {"status": "skipped", "batch_id": existing[0], "stored_rows": existing[1],
                        "inspection": report}
            batch_id = connection.execute(
                "INSERT INTO import_batches(source_file, source_sha256, mapping_sha256, parser_version, "
                "importer_version, sheet_name, imported_at, mapping_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source.name, *identity, config["sheet"], datetime.now(timezone.utc).isoformat(), mapping_json)
            ).lastrowid
            columns = ("batch_id", "source_row", *CORE_FIELDS, "raw_json", "selected_json",
                       "issues_json", "duplicate_first_row")
            insert_sql = f"INSERT INTO rules({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
            stored_rows = 0

            def store_row(row):
                nonlocal stored_rows
                if any(issue["severity"] == "error" for issue in row["issues"]):
                    return  # Finish inspecting all rows; reject the batch below.
                selected = row["selected"]
                if selected["sec_code"] is None:
                    raise ValueError(f"{row['source_row']}행 SEC 코드가 비어 있음; 전체 적재 취소")
                for name in CORE_FIELDS:
                    value = selected.get(name)
                    if CORE_TYPES[name] == "integer" and value is not None and not -(2**63) <= value < 2**63:
                        raise ValueError(f"{row['source_row']}행 {name}: SQLite 정수 범위를 벗어남")
                connection.execute(insert_sql, (
                    batch_id, row["source_row"], *(selected.get(name) for name in CORE_FIELDS),
                    encode_json(row["raw"]), encode_json(selected), encode_json(row["issues"]),
                    row["duplicate_first_row"],
                ))
                stored_rows += 1

            report = inspect_workbook(source, config, preview_limit, row_sink=store_row, source_bytes=source_bytes)
            if report["errors"]:
                raise InspectionError(report)
            if not stored_rows:
                raise ValueError("저장할 데이터 행이 없음; 빈 가져오기를 취소함")
            connection.execute("UPDATE import_batches SET row_count=?, inspection_json=? WHERE id=?",
                               (stored_rows, encode_json(report), batch_id))
            connection.commit()
            return {"status": "imported", "batch_id": batch_id, "stored_rows": stored_rows, "inspection": report}
        except BaseException:
            connection.rollback()
            raise


def lookup_rules(database, sec_code, batch_id):
    """Query one explicit snapshot. A miss is NOT_FOUND, never a PASS verdict."""
    if not isinstance(sec_code, str) or not re.fullmatch(r"[0-9]{8}", sec_code.strip()):
        raise ValueError("조회 SEC 코드는 원본과 같은 대시 없는 8자리 문자열이어야 함")
    sec_code = sec_code.strip()
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
            "SELECT * FROM rules WHERE batch_id=? AND sec_code=? ORDER BY rule_adminno, rule_seqno, source_row",
            (batch_id, sec_code),
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            for name in ("raw", "selected", "issues"):
                item[name] = json.loads(item.pop(name + "_json"))
            results.append(item)
        return {"batch_id": batch_id, "sec_code": sec_code, "source_file": batch["source_file"],
                "source_sha256": batch["source_sha256"], "mapping_sha256": batch["mapping_sha256"],
                "match_status": "MATCHED" if results else "NOT_FOUND", "rules": results}
