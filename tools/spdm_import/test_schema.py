"""Blank-schema checks only: no CSV/JSON fixtures or synthetic data records."""

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from db_common import connect_database, ensure_empty, objects, validate_schema
from import_data import import_files
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

    def test_generated_column_and_provided_primary_keys_are_retained(self):
        initialize_database(self.db)
        with closing(connect_database(self.db, read_only=True)) as con:
            columns = {row[1]: row for row in con.execute('PRAGMA table_xinfo(checkpoints)')}
            self.assertEqual(3, columns['savefolder'][6])
            ddl = con.execute("SELECT sql FROM sqlite_master WHERE name='parts'").fetchone()[0]
            self.assertNotIn('AUTOINCREMENT', ddl)

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
        sql_path = Path(__file__).with_name('queries_sqlite.sql')
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


if __name__ == '__main__':
    unittest.main()
