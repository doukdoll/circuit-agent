"""Python file dialogs for blank schema creation or one real CSV/JSON import."""

import csv
from pathlib import Path
import sqlite3
import sys

from db_common import SCHEMA_PATH, distinct_paths
from import_data import import_files
from init_db import initialize_database


def default_output_dir(app_dir=None):
    app = Path(app_dir) if app_dir is not None else Path(__file__).resolve().parent
    root = app.parent.parent if app.name == 'spdm_json' and app.parent.name == 'app' else app
    return root / 'local-output'


def run_setup(dialogs, messages, *, app_dir=None):
    try:
        import_real = messages.askyesnocancel(
            'Circuit Review DB',
            '원본 CSV와 분석 JSON도 함께 적재할까요?\n\n'
            '예: 실제 CSV + JSON 선택 후 최초 적재\n'
            '아니오: 14개 테이블만 있는 빈 DB 생성\n'
            '취소: 종료',
        )
        if import_real is None:
            return 0
        csv_path = analysis_path = None
        if import_real:
            csv_path = dialogs.askopenfilename(title='1. 원본 23컬럼 CSV 선택',
                                               filetypes=(('CSV 파일', '*.csv'),))
            if not csv_path:
                return 0
            analysis_path = dialogs.askopenfilename(title='2. 대응하는 분석 JSON 선택',
                                                    filetypes=(('JSON 파일', '*.json'),))
            if not analysis_path:
                return 0
        output = default_output_dir(app_dir)
        output.mkdir(parents=True, exist_ok=True)
        database = dialogs.asksaveasfilename(
            title='빈 Circuit Review DB 저장 위치', initialdir=str(output),
            initialfile='circuit_review_v2.db', defaultextension='.db',
            filetypes=(('SQLite DB', '*.db'), ('SQLite DB', '*.sqlite')),
            confirmoverwrite=False,
        )
        if not database:
            return 0
        distinct_paths(database, csv_path, analysis_path, SCHEMA_PATH)
        initialized = initialize_database(database)
        if not import_real:
            messages.showinfo('빈 DB 준비 완료',
                              f"테이블: {initialized['tables']}개\n데이터: 0행\n\nDB:\n{initialized['database']}")
            return 0
        result = import_files(database, csv_path, analysis_path)
        messages.showinfo(
            '실제 데이터 적재 완료',
            f"부품: {result['parts']:,}개\n체크포인트: {result['checkpoints']:,}개\n"
            f"세부 규칙: {result['checks']:,}개\n파라미터: {result['parameters']:,}개\n"
            f"요구 사실: {result['facts']:,}개\n근거: {result['evidence']:,}개\n"
            f"분석 이슈: {result['issues']:,}개\n\nDB:\n{result['database']}",
        )
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error, csv.Error, RecursionError) as error:
        messages.showerror('DB 작업 오류',
                           f'{error}\n\n이번 데이터 적재는 전체 취소됩니다.\n'
                           '새로 만든 DB에는 빈 테이블만 남을 수 있습니다.')
        return 2


def main():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        print('Python 설치의 Tcl/Tk 및 IDLE 옵션이 필요합니다.', file=sys.stderr)
        return 2
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f'파일 선택 창을 열 수 없습니다: {error}', file=sys.stderr)
        return 2
    root.withdraw()
    try:
        return run_setup(filedialog, messagebox)
    finally:
        root.destroy()


if __name__ == '__main__':
    sys.exit(main())
