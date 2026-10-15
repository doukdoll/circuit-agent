"""Inspect fixed-schema analysis JSON with Python's standard library only."""

import argparse
import json
from pathlib import Path
import sys

from json_rules import parse_analysis
from sqlite_store import distinct_paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="전처리 analysis JSON 구조·내용 점검 (DB 저장 없음)")
    parser.add_argument("input", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--preview", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        distinct_paths(args.input, args.report, Path(__file__).with_name("analysis.schema.json"))
        report = parse_analysis(args.input, args.preview).report
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(f"체크포인트={report['checkpoint_count']}, 세부규칙={report['data_rows']}, "
              f"SEC={report['valid_unique_sec_codes']}, 오류={report['errors']}, 경고={report['warnings']}")
        return 2 if report["errors"] else 0
    except (OSError, ValueError, RecursionError) as error:
        print(f"JSON 점검 오류: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
