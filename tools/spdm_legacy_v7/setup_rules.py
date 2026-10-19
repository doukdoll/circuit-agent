"""Choose a JSON and SQLite file, then use the existing local importer."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import io
import json
from pathlib import Path
import sys

from import_rules import main as import_main


def default_output_dir(app_dir=None):
    app = Path(app_dir) if app_dir is not None else Path(__file__).resolve().parent
    root = app.parent.parent if app.name == "spdm_json" and app.parent.name == "app" else app
    return root / "local-output"


def run_setup(dialogs, messages, *, app_dir=None):
    """Keep file-dialog interaction separate so imports can be tested headlessly."""
    try:
        source = dialogs.askopenfilename(
            title="1. 원본 규칙 JSON 선택",
            filetypes=(("JSON 파일", "*.json"), ("모든 파일", "*.*")),
        )
        if not source:
            return 0

        output = default_output_dir(app_dir)
        output.mkdir(parents=True, exist_ok=True)
        selected = dialogs.asksaveasfilename(
            title="2. 규칙 DB 저장 위치 선택",
            initialdir=str(output),
            initialfile="rules-v7.sqlite",
            defaultextension=".sqlite",
            filetypes=(("SQLite DB", "*.sqlite"), ("SQLite DB", "*.db")),
            confirmoverwrite=False,
        )
        if not selected:
            return 0
        database = Path(selected)
        if database.exists() and not messages.askyesno(
            "기존 규칙 전체 교체",
            f"선택한 DB:\n{database}\n\n"
            "이 DB의 현재 규칙을 선택한 JSON 전체로 교체합니다.\n"
            "JSON에 없는 기존 규칙도 제거됩니다. 계속할까요?\n\n"
            "이전 스키마의 DB라면 새 파일명을 선택하세요.",
            default="no",
        ):
            return 0

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        report = database.with_name(f"{database.stem}_import_{stamp}.json")
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = import_main([
                str(source), "--db", str(database), "--report", str(report), "--preview", "3",
            ])

        if code:
            detail = stderr.getvalue().strip() or stdout.getvalue().strip()
            if report.exists():
                result = json.loads(report.read_text(encoding="utf-8"))
                errors = [issue for issue in result["inspection"]["issues"]
                          if issue["severity"] == "error"]
                detail += "\n\n" + "\n".join(
                    f"{issue['path']}: {issue['reason']}" for issue in errors[:5]
                )
                detail += f"\n\n보고서:\n{report}"
            if stderr.getvalue().startswith("DB 최신 규칙 반영은 완료됨"):
                messages.showwarning("DB 적재 완료 · 보고서 저장 오류", detail)
            else:
                messages.showerror("DB 작업 결과 확인", detail)
            return code

        result = json.loads(report.read_text(encoding="utf-8"))
        messages.showinfo(
            "규칙 DB 적재 완료",
            f"상태: {result['status']}\n"
            f"체크포인트: {result['stored_checkpoints']:,}개\n"
            f"세부 규칙: {result['stored_rows']:,}개\n"
            f"경고: {result['inspection']['warnings']:,}개\n\n"
            f"저장된 DB:\n{database}\n\n보고서:\n{report}",
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as error:
        messages.showerror("실행 오류", str(error))
        return 2


def main():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        print("Python 설치에서 Tcl/Tk 및 IDLE 옵션을 추가한 뒤 다시 실행하세요.", file=sys.stderr)
        return 2

    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"파일 선택 창을 열 수 없습니다: {error}", file=sys.stderr)
        return 2
    root.withdraw()
    try:
        return run_setup(filedialog, messagebox)
    finally:
        root.destroy()


if __name__ == "__main__":
    sys.exit(main())
