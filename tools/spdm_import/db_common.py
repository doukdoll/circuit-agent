"""SQLite identity, schema checks and connection settings; no data generation."""

from contextlib import closing
from functools import lru_cache
from pathlib import Path
import sqlite3

APPLICATION_ID = 0x43525657
SCHEMA_VERSION = 3
SCHEMA_PATH = Path(__file__).with_name("schema_sqlite.sql")


def distinct_paths(*paths):
    paths = [Path(path) for path in paths if path is not None]
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            if left.resolve() == right.resolve() or (
                left.exists() and right.exists() and left.samefile(right)
            ):
                raise ValueError("DB·CSV·JSON·스키마 파일 경로는 서로 달라야 합니다.")


def connect_database(database, *, create=False, read_only=False):
    if sqlite3.sqlite_version_info < (3, 31, 0):
        raise RuntimeError("SQLite 3.31 이상이 필요합니다.")
    mode = "ro" if read_only else "rwc" if create else "rw"
    connection = sqlite3.connect(Path(database).resolve().as_uri() + f"?mode={mode}",
                                 uri=True, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("SELECT json_valid('{}')").fetchone()
    except BaseException:
        connection.close()
        raise
    return connection


def objects(connection):
    return {(kind, name): (table, sql) for kind, name, table, sql in connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
    )}


def execute_schema(connection):
    statement = ""
    for line in SCHEMA_PATH.read_text(encoding="utf-8").splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise ValueError("스키마 SQL이 완전한 문장으로 끝나지 않습니다.")


@lru_cache(maxsize=1)
def expected_objects():
    with closing(sqlite3.connect(":memory:")) as reference:
        execute_schema(reference)
        return objects(reference)


def validate_schema(connection):
    if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
        raise ValueError("새 Circuit Review DB가 아닙니다. init_db.py로 별도의 새 DB를 만드세요.")
    if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        raise ValueError(
            f"지원하지 않는 Circuit Review 스키마 버전입니다. 현재 버전은 {SCHEMA_VERSION}입니다. "
            "기존 DB는 자동 변환하지 않으므로 별도 새 DB 파일명을 선택하세요."
        )
    if objects(connection) != expected_objects():
        raise ValueError("DB의 테이블·인덱스·트리거가 동봉 스키마와 다릅니다. 자동 변환하지 않습니다.")


def ensure_empty(connection):
    for (kind, name) in expected_objects():
        if kind == "table" and connection.execute(f'SELECT EXISTS(SELECT 1 FROM "{name}")').fetchone()[0]:
            raise ValueError(f"{name} 테이블에 데이터가 있습니다. 최초 적재에는 새 빈 DB가 필요합니다.")
