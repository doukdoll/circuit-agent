"""Offline acceptance checks on the machine where this script is executed."""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile

from sqlite_store import SCHEMA_VERSION, distinct_paths


def verify(source=None, *, expect_windows=False):
    app = Path(__file__).resolve().parent
    windows = platform.system() == "Windows"
    report = {"status": "failed", "system": platform.system(), "release": platform.release(),
              "python": platform.python_version(), "python_executable": sys.executable,
              "sqlite": sqlite3.sqlite_version, "windows_verified": False, "checks": {}}
    try:
        if expect_windows and not windows:
            raise ValueError("실제 Windows가 아님; Windows 검증 성공으로 기록할 수 없음")
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"

        def run(*args, expected=0):
            result = subprocess.run([sys.executable, "-S", *map(str, args)], cwd=app,
                                    env=child_env, capture_output=True, encoding="utf-8", errors="replace")
            if result.returncode != expected:
                raise ValueError(f"{Path(str(args[0])).name}: 종료 {result.returncode}, 예상 {expected}: "
                                 f"{result.stderr[-2000:]}")
            return result

        suite = run("-m", "unittest", "discover", "-s", app, "-p", "test_json_rules.py", "-v")
        report["checks"]["unit_tests"] = True
        report["unit_test_log"] = suite.stderr
        if source is None:
            from test_json_rules import synthetic_record
            raw = json.dumps([synthetic_record(), synthetic_record("1234-567890", "synthetic:2")], ensure_ascii=False).encode()
            report["input_kind"] = "synthetic"
        else:
            raw = Path(source).read_bytes()
            report["input_kind"] = "provided_file"
        original_hash = hashlib.sha256(raw).hexdigest()
        reference = json.loads(raw.decode("utf-8-sig"))
        expected_checks = [check for record in reference if record["analysis"] is not None
                           for check in record["analysis"]["checks"]]
        with tempfile.TemporaryDirectory(prefix="SPDM 한글 # 환경 ") as temporary:
            root = Path(temporary)
            input_path, db = root / "입력 규칙.json", root / "규칙 DB.sqlite"
            inspection_path, import_path = root / "점검.json", root / "저장.json"
            input_path.write_bytes(raw)
            run(app / "inspect_json_rules.py", input_path, "--report", inspection_path, "--preview", 1)
            run(app / "import_rules.py", input_path, "--db", db, "--report", import_path, "--preview", 1)
            imported = json.loads(import_path.read_text(encoding="utf-8"))
            if imported["stored_rows"] != len(expected_checks):
                raise ValueError("세부 규칙 전체 저장 건수가 다름")
            for index, sec in enumerate(sorted({record["sec_code"] for record in reference})):
                expected = [check for check in expected_checks if check["sec_code"] == sec]
                query_path = root / f"조회 결과 {index}.json"
                run(app / "query_rules.py", db, "--sec-code", sec,
                    "--output", query_path, expected=0 if expected else 3)
                queried = json.loads(query_path.read_text(encoding="utf-8"))
                if [item["raw"] for item in queried["rules"]] != expected:
                    raise ValueError("SEC 조회에서 원문 또는 규칙 순서가 달라짐")
                for actual, check in zip(queried["rules"], expected):
                    for name in ("parameters", "required_design_facts", "evidence"):
                        if actual[name] != check[name]:
                            raise ValueError(f"구조화 필드 {name} 보존 실패")
                    if actual["design_value"] is not None:
                        raise ValueError("확인할 설계 항목이 실제 설계값으로 변환됨")
            with closing(sqlite3.connect(db)) as connection:
                originals = connection.execute("SELECT raw_json FROM checkpoints ORDER BY source_record_index").fetchall()
                if [json.loads(row[0]) for row in originals] != reference:
                    raise ValueError("체크포인트 원문/summary/issues 보존 실패")
                if connection.execute("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("외래키 무결성 오류")
                if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                    raise ValueError("스키마 버전 오류")
            report["checks"].update(full_import=True, all_sec_queries=True, structured_values=True,
                                    parent_raw_issues=True, foreign_keys=True, unicode_space_paths=True)
            run(app / "import_rules.py", input_path, "--db", db, "--report", import_path, "--preview", 0)
            repeated = json.loads(import_path.read_text(encoding="utf-8"))
            if repeated["status"] != "replaced" or repeated["stored_rows"] != len(expected_checks):
                raise ValueError("동일 파일 재실행 시 최신 규칙 유지 실패")
            report["checks"]["repeat_without_accumulation"] = True
            changed = json.loads(raw.decode("utf-8-sig"))
            changed[0]["status"] += "-environment-test"
            input_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            run(app / "import_rules.py", input_path, "--db", db, "--report", import_path)
            changed_import = json.loads(import_path.read_text(encoding="utf-8"))
            if changed_import["status"] != "replaced":
                raise ValueError("내용 변경 시 최신 규칙 교체 실패")
            with closing(sqlite3.connect(db)) as connection:
                current = connection.execute("SELECT raw_json FROM checkpoints ORDER BY source_record_index").fetchall()
                if [json.loads(row[0]) for row in current] != changed:
                    raise ValueError("최신 JSON 전체 교체 실패")
                if connection.execute("SELECT COUNT(*) FROM rules").fetchone()[0] != len(expected_checks):
                    raise ValueError("이전 규칙이 누적됨")
            report["checks"]["changed_input_replaces_current"] = True
            before_invalid = db.read_bytes()
            del changed[0]["row_uid"]
            input_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            run(app / "import_rules.py", input_path, "--db", db, "--report", import_path, expected=2)
            if json.loads(import_path.read_text(encoding="utf-8"))["status"] != "rejected":
                raise ValueError("잘못된 JSON 거부 실패")
            if db.read_bytes() != before_invalid:
                raise ValueError("잘못된 입력으로 DB가 변경됨")
            report["checks"]["invalid_input_preserves_db"] = True
            report.update(checkpoint_count=len(reference), rule_count=len(expected_checks),
                          sec_count=len({record["sec_code"] for record in reference}),
                          source_issue_count=imported["inspection"]["source_issue_count"])
        if source is not None and hashlib.sha256(Path(source).read_bytes()).hexdigest() != original_hash:
            raise ValueError("원본 입력 파일이 변경됨")
        report["checks"]["original_unchanged"] = True
        report.update(status="passed", windows_verified=windows)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        report["error"] = str(error)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="현재 PC의 JSON 저장·조회·경로·재실행 검증 (외부 패키지 불필요)")
    parser.add_argument("--input", type=Path, help="생략하면 가상 데이터만 검증")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expect-windows", action="store_true", help="실제 Windows가 아니면 실패 처리")
    args = parser.parse_args(argv)
    try:
        distinct_paths(args.input, Path(__file__).with_name("analysis.schema.json"), args.report)
        result = verify(args.input, expect_windows=args.expect_windows)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"상태={result['status']}, OS={result['system']}, Windows검증={result['windows_verified']}, 보고서={args.report}")
        return 0 if result["status"] == "passed" else 2
    except (OSError, ValueError) as error:
        print(f"환경 점검 오류: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
