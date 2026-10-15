"""CLI: look up the complete rule list for a BOM-resolved SEC code."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from sqlite_store import distinct_paths, lookup_rules


def main(argv=None):
    parser = argparse.ArgumentParser(description="SQLite의 최신 규칙을 SEC 코드별 전체 조회")
    parser.add_argument("db", type=Path)
    parser.add_argument("--sec-code", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        distinct_paths(args.db, args.output)
        result = lookup_rules(args.db, args.sec_code)
        content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
            print(f"상태={result['match_status']}, 규칙={len(result['rules'])}, 출력={args.output}")
        else:
            print(content)
        return 0 if result["rules"] else 3
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"조회 오류: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
