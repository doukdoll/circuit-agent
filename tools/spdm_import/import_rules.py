"""CLI: import every selected rule row into a local SQLite snapshot."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from inspect_rules import read_mapping
from sqlite_store import InspectionError, distinct_paths, import_workbook


def main(argv=None):
    parser = argparse.ArgumentParser(description="SPDM 병합/정제 xlsx → 로컬 SQLite 규칙 DB")
    parser.add_argument("input", type=Path)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, default=Path(__file__).with_name("mapping.json"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--preview", type=int, default=10)
    args = parser.parse_args(argv)
    result = None
    try:
        distinct_paths(args.input, args.mapping, args.db, args.report)
        config = read_mapping(args.mapping)
        try:
            result = import_workbook(args.input, args.db, config, args.preview)
        except InspectionError as error:
            result = {"status": "rejected", "stored_rows": 0, "inspection": error.report}
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(f"상태={result['status']}, batch_id={result.get('batch_id')}, "
              f"저장행={result['stored_rows']}, 오류={result['inspection']['errors']}, "
              f"경고={result['inspection']['warnings']}, "
              f"중복후보={len(result['inspection']['duplicate_candidates'])}")
        return 2 if result["status"] == "rejected" else 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError, sqlite3.Error, BadZipFile, InvalidFileException) as error:
        if result is not None and result.get("status") in {"imported", "skipped"}:
            print(f"DB 적재는 완료됨(batch_id={result['batch_id']}); 보고서 기록 실패: {error}", file=sys.stderr)
        else:
            print(f"적재 오류(이번 가져오기 저장 없음): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
