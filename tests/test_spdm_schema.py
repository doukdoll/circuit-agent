"""Blank schema and scalar comparison checks; no CSV/JSON records generated."""

import ast
from contextlib import closing
from pathlib import Path
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

APP_DIR = Path(os.environ.get('CIRCUIT_REVIEW_APP_DIR',
                             Path(__file__).resolve().parents[1] / 'tools' / 'spdm_import')).resolve()
sys.path.insert(0, str(APP_DIR))

from db_common import SCHEMA_VERSION, connect_database, ensure_empty, objects, validate_schema
from import_data import (describe_shared_difference, import_files, normalized_shared_value,
                         optional_shared_text, shared_part_error)
from init_db import initialize_database
from setup_rules import run_setup


class BlankSchemaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='Circuit Review 빈 DB # ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'circuit_review.db'

    def test_fourteen_tables_two_triggers_and_no_data(self):
        result = initialize_database(self.db)
        self.assertEqual('initialized', result['status'])
        with closing(connect_database(self.db, read_only=True)) as con:
            validate_schema(con)
            ensure_empty(con)
            self.assertEqual(14, sum(kind == 'table' for kind, name in objects(con)))
            self.assertEqual(2, sum(kind == 'trigger' for kind, name in objects(con)))
            self.assertEqual(1, con.execute('PRAGMA foreign_keys').fetchone()[0])
            self.assertEqual([], con.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual('ok', con.execute('PRAGMA integrity_check').fetchone()[0])

    def test_reinitialization_is_read_only_for_existing_blank_schema(self):
        initialize_database(self.db)
        before = self.db.read_bytes()
        self.assertEqual('already_initialized', initialize_database(self.db)['status'])
        self.assertEqual(before, self.db.read_bytes())

    def test_savefolder_is_regular_text_and_primary_keys_are_retained(self):
        initialize_database(self.db)
        with closing(connect_database(self.db, read_only=True)) as con:
            columns = {row[1]: row for row in con.execute('PRAGMA table_xinfo(checkpoints)')}
            self.assertEqual('TEXT', columns['savefolder'][2])
            self.assertEqual(0, columns['savefolder'][6])
            ddl = con.execute("SELECT sql FROM sqlite_master WHERE name='parts'").fetchone()[0]
            self.assertNotIn('AUTOINCREMENT', ddl)

    def test_ldrc_metadata_is_owned_by_checkpoints_in_format_three(self):
        initialize_database(self.db)
        ldrc_columns = {'ldrc_check_tp', 'ldrc_regist_tp', 'ldrc_check_date_serial',
                        'ldrc_checker_emp_no', 'ldrc_id'}
        with closing(connect_database(self.db, read_only=True)) as con:
            self.assertEqual(3, SCHEMA_VERSION)
            self.assertEqual(3, con.execute('PRAGMA user_version').fetchone()[0])
            part_columns = {row[1] for row in con.execute('PRAGMA table_info(parts)')}
            checkpoint_columns = {row[1] for row in con.execute('PRAGMA table_info(checkpoints)')}
            self.assertTrue(ldrc_columns.isdisjoint(part_columns))
            self.assertTrue(ldrc_columns <= checkpoint_columns)
            ensure_empty(con)

    def test_previous_formats_are_rejected_without_changing_the_database(self):
        initialize_database(self.db)
        for version in (1, 2):
            with self.subTest(version=version):
                with closing(sqlite3.connect(self.db)) as con:
                    con.execute(f'PRAGMA user_version = {version}')
                before = self.db.read_bytes()
                with self.assertRaisesRegex(ValueError, '별도 새 DB 파일명'):
                    initialize_database(self.db)
                self.assertEqual(before, self.db.read_bytes())
                with closing(connect_database(self.db, read_only=True)) as con:
                    with self.assertRaisesRegex(ValueError, '별도 새 DB 파일명'):
                        validate_schema(con)

    def test_import_sql_compiles_against_schema_without_inserting_records(self):
        initialize_database(self.db)
        module = ast.parse((APP_DIR / 'import_data.py').read_text(encoding='utf-8'))
        count = 0
        with closing(connect_database(self.db, read_only=True)) as con:
            for node in ast.walk(module):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'execute' and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    continue
                sql = node.args[0].value
                if not sql.lstrip().upper().startswith(('INSERT ', 'UPDATE ')):
                    continue
                # EXPLAIN only compiles statements, including CHECK/FK code;
                # it never executes these inserts and generates no records.
                con.execute('EXPLAIN ' + sql, (None,) * sql.count('?')).fetchall()
                count += 1
            self.assertEqual(9, count)
            ensure_empty(con)

    def test_foreign_database_is_not_modified(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('CREATE TABLE unrelated_definition (value TEXT)')
            con.commit()
        before = self.db.read_bytes()
        with self.assertRaises(ValueError):
            initialize_database(self.db)
        self.assertEqual(before, self.db.read_bytes())

    def test_changed_schema_is_rejected_without_repair(self):
        initialize_database(self.db)
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('DROP TRIGGER trg_verification_result_match_insert')
            con.commit()
        before = self.db.read_bytes()
        with self.assertRaises(ValueError):
            initialize_database(self.db)
        self.assertEqual(before, self.db.read_bytes())

    def test_ddl_error_rolls_back_every_definition(self):
        def fail(con):
            con.execute('CREATE TABLE interrupted_definition (value TEXT)')
            raise ValueError('DDL interrupted')
        with patch('init_db.execute_schema', side_effect=fail):
            with self.assertRaises(ValueError):
                initialize_database(self.db)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual({}, objects(con))

    def test_missing_real_sources_do_not_change_blank_database(self):
        initialize_database(self.db)
        before = self.db.read_bytes()
        with self.assertRaises(ValueError):
            import_files(self.db, self.root / 'missing.csv', self.root / 'missing.json')
        self.assertEqual(before, self.db.read_bytes())

    def test_gui_can_initialize_without_any_data(self):
        dialogs, messages = Mock(), Mock()
        messages.askyesnocancel.return_value = False
        dialogs.asksaveasfilename.return_value = str(self.db)
        self.assertEqual(0, run_setup(dialogs, messages, app_dir=self.root))
        with closing(connect_database(self.db, read_only=True)) as con:
            ensure_empty(con)
        self.assertIn('데이터: 0행', messages.showinfo.call_args.args[1])
        dialogs.askopenfilename.assert_not_called()

    def test_gui_cancel_does_not_create_a_database(self):
        dialogs, messages = Mock(), Mock()
        messages.askyesnocancel.return_value = None
        self.assertEqual(0, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual([], list(self.root.iterdir()))

    def test_query_examples_execute_read_only_on_blank_schema(self):
        initialize_database(self.db)
        sql_path = APP_DIR / 'queries_sqlite.sql'
        with closing(connect_database(self.db, read_only=True)) as con:
            statement = ''
            count = 0
            for line in sql_path.read_text(encoding='utf-8').splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    con.execute(statement, {'sec_code': None, 'design_id': None, 'run_id': None}).fetchall()
                    statement = ''
                    count += 1
            self.assertEqual(6, count)
            ensure_empty(con)


class SharedComparisonTest(unittest.TestCase):
    def test_equal_serial_date_spellings_compare_equal_without_rewriting(self):
        original = ' 1.000 '
        for column in (4,):
            self.assertEqual(normalized_shared_value(column, original), normalized_shared_value(column, '1'))
        self.assertEqual(' 1.000 ', original)

    def test_different_dates_are_not_rounded_to_the_same_value(self):
        self.assertNotEqual(normalized_shared_value(4, '1.00000000000000001'),
                            normalized_shared_value(4, '1.00000000000000002'))

    def test_optional_missing_text_maps_to_sql_null_consistently(self):
        for column in (5, 6):
            for text in ('', ' ', '\t', '\u00a0'):
                with self.subTest(column=column, text=repr(text)):
                    self.assertIsNone(normalized_shared_value(column, text))
                    self.assertIsNone(optional_shared_text(text))

    def test_identifiers_and_nonempty_labels_remain_exact(self):
        for column in (2, 3, 5, 6):
            self.assertNotEqual(normalized_shared_value(column, 'value'),
                                normalized_shared_value(column, 'value '))
            self.assertNotEqual(normalized_shared_value(column, 'Value'),
                                normalized_shared_value(column, 'value'))
        self.assertEqual(' value ', optional_shared_text(' value '))

    def test_error_identifies_rows_columns_and_invisible_characters(self):
        detail = describe_shared_difference(5, '', '\t')
        message = shared_part_error(2, 31, [detail])
        self.assertIn('최초 2번 / 현재 31번', message)
        self.assertIn('F열 maker', message)
        self.assertIn("현재='\\t'", message)

if __name__ == '__main__':
    unittest.main()
