"""Initialize the supplied 14-table schema without creating any records."""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

from db_common import (APPLICATION_ID, SCHEMA_PATH, SCHEMA_VERSION, connect_database,
                       distinct_paths, ensure_empty, execute_schema, objects, validate_schema)


def initialize_database(database):
    database = Path(database)
    distinct_paths(database, SCHEMA_PATH)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect_database(database, create=True)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            if objects(connection):
                validate_schema(connection)
                ensure_empty(connection)
                status = "already_initialized"
            else:
                if connection.execute("PRAGMA application_id").fetchone()[0] not in (0, APPLICATION_ID):
                    raise ValueError("다른 프로그램의 DB입니다. 별도 새 파일을 사용하세요.")
                if connection.execute("PRAGMA user_version").fetchone()[0] not in (0, SCHEMA_VERSION):
                    raise ValueError("다른 버전의 DB입니다. 별도 새 파일을 사용하세요.")
                execute_schema(connection)
                connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                validate_schema(connection)
                ensure_empty(connection)
                status = "initialized"
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return {"status": status, "database": str(database.resolve()), "tables": 14}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = initialize_database(args.db)
        print(f"상태={result['status']}, 테이블={result['tables']}, DB={result['database']}")
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"초기화 오류: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
