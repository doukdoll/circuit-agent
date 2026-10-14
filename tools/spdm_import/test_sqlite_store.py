"""SQLite integration tests using synthetic workbooks only."""

from contextlib import closing, redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from openpyxl import Workbook

from import_rules import main as import_main
from inspect_rules import read_mapping
from query_rules import main as query_main
from sqlite_store import InspectionError, import_workbook, lookup_rules
from test_inspect_rules import HEADERS, example_row


class SQLiteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic.xlsx"
        self.db = self.root / "rules.sqlite"
        self.mapping = Path(__file__).with_name("mapping.json")
        self.config = read_mapping(self.mapping)

    def write_book(self, rows, headers=None):
        book = Workbook()
        book.active.title = "병합결과"
        book.active.append(headers or HEADERS)
        for row in rows:
            book.active.append(row)
        book.save(self.source)
        book.close()

    def counts(self):
        with closing(sqlite3.connect(self.db)) as connection:
            return tuple(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                         for name in ("import_batches", "rules"))

    def test_all_rows_stored_beyond_preview_with_source_and_typed_columns(self):
        rows = []
        for seq in range(25):
            row = example_row()
            row[8] = seq
            rows.append(row)
        rows[20][9] = None
        rows.insert(1, [None] * 23)
        self.write_book(rows)
        before = self.source.read_bytes()
        result = import_workbook(self.source, self.db, self.config, preview_limit=1)
        self.assertEqual("imported", result["status"])
        self.assertEqual(25, result["stored_rows"])
        self.assertEqual(1, len(result["inspection"]["preview"]))
        matched = lookup_rules(self.db, "03438806", result["batch_id"])
        self.assertEqual(25, len(matched["rules"]))
        first = matched["rules"][0]
        self.assertEqual("MATCHED", matched["match_status"])
        self.assertEqual("03438806", first["sec_code"])
        self.assertEqual(8, first["part_seqno"])
        self.assertEqual(0, first["rule_seqno"])
        self.assertEqual("0", first["design_value"])
        self.assertEqual("EN|KO\n최소 10 kΩ ±5%", first["checkpoint"])
        self.assertEqual(example_row()[9], first["raw"]["checkpoint"])
        self.assertIsNone(matched["rules"][20]["checkpoint"])
        self.assertEqual(4, matched["rules"][1]["source_row"])
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(hashlib.sha256(before).hexdigest(), matched["source_sha256"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(("text", "integer"), connection.execute(
                "SELECT typeof(sec_code), typeof(rule_seqno) FROM rules LIMIT 1").fetchone())

    def test_duplicate_candidates_and_warnings_are_retained(self):
        first, second = example_row(), example_row()
        first[16] = "z"
        second[9] = "別の規則 — 다른 조건"
        self.write_book([first, second])
        result = import_workbook(self.source, self.db, self.config)
        rules = lookup_rules(self.db, "03438806", result["batch_id"])["rules"]
        self.assertEqual(2, len(rules))
        self.assertEqual(2, rules[1]["duplicate_first_row"])
        self.assertEqual("warning", rules[0]["issues"][0]["severity"])
        self.assertEqual("z", rules[0]["category"])
        self.assertEqual(1, len(result["inspection"]["duplicate_candidates"]))

    def test_identical_bytes_mapping_and_version_skip_even_when_renamed(self):
        self.write_book([example_row()])
        first = import_workbook(self.source, self.db, self.config)
        copy = self.root / "renamed.xlsx"
        shutil.copyfile(self.source, copy)
        second = import_workbook(copy, self.db, self.config, preview_limit=0)
        self.assertEqual("skipped", second["status"])
        self.assertEqual(first["batch_id"], second["batch_id"])
        self.assertEqual([], second["inspection"]["preview"])
        self.assertEqual("renamed.xlsx", second["inspection"]["source_file"])
        self.assertEqual((1, 1), self.counts())

    def test_changed_mapping_makes_separate_snapshot_with_extra_fields(self):
        self.write_book([example_row() + ["정제 결과"]], HEADERS + ["Checkpoint_cleaned"])
        first = import_workbook(self.source, self.db, self.config)
        config = deepcopy(self.config)
        field = next(field for field in config["fields"] if field["name"] == "checkpoint")
        field.pop("column")
        field["header"] = "Checkpoint_cleaned"
        config["fields"].append({"name": "ldrc_check_tp", "header": "ldrc_check_tp", "type": "text"})
        second = import_workbook(self.source, self.db, config)
        self.assertNotEqual(first["batch_id"], second["batch_id"])
        original = lookup_rules(self.db, "03438806", first["batch_id"])["rules"][0]
        cleaned = lookup_rules(self.db, "03438806", second["batch_id"])["rules"][0]
        self.assertNotEqual(original["checkpoint"], cleaned["checkpoint"])
        self.assertEqual("정제 결과", cleaned["checkpoint"])
        self.assertEqual("N", cleaned["selected"]["ldrc_check_tp"])
        self.assertEqual((2, 2), self.counts())

    def test_changed_file_new_snapshot_does_not_mix_rule_versions(self):
        self.write_book([example_row()])
        first = import_workbook(self.source, self.db, self.config)
        row = example_row()
        row[9] = "새 규칙"
        self.write_book([row])
        second = import_workbook(self.source, self.db, self.config)
        self.assertEqual("새 규칙", lookup_rules(self.db, "03438806", second["batch_id"])["rules"][0]["checkpoint"])
        self.assertNotEqual("새 규칙", lookup_rules(self.db, "03438806", first["batch_id"])["rules"][0]["checkpoint"])
        self.assertEqual((2, 2), self.counts())

    def test_validation_error_after_valid_rows_rolls_back_entire_batch(self):
        self.write_book([example_row()])
        import_workbook(self.source, self.db, self.config)
        bad = example_row()
        bad[2] = 3438806
        self.write_book([example_row(), bad, bad])
        with self.assertRaises(InspectionError) as caught:
            import_workbook(self.source, self.db, self.config, preview_limit=0)
        self.assertEqual(2, caught.exception.report["errors"])
        self.assertEqual(3, caught.exception.report["data_rows"])
        self.assertEqual((1, 1), self.counts())

    def test_sql_failure_after_insert_rolls_back_and_preserves_prior_batch(self):
        self.write_book([example_row()])
        import_workbook(self.source, self.db, self.config)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("""CREATE TRIGGER fail_rule BEFORE INSERT ON rules
                WHEN NEW.checkpoint='explode' BEGIN SELECT RAISE(ABORT, 'test write failure'); END""")
            connection.commit()
        bad = example_row()
        bad[9] = "explode"
        self.write_book([example_row(), bad])
        with self.assertRaises(sqlite3.IntegrityError):
            import_workbook(self.source, self.db, self.config)
        self.assertEqual((1, 1), self.counts())

    def test_unknown_sec_not_found_and_unknown_batch_error(self):
        self.write_book([example_row()])
        result = import_workbook(self.source, self.db, self.config)
        missing = lookup_rules(self.db, "99999999", result["batch_id"])
        self.assertEqual("NOT_FOUND", missing["match_status"])
        self.assertEqual([], missing["rules"])
        with self.assertRaises(ValueError):
            lookup_rules(self.db, "03438806", 999)
        with self.assertRaises(ValueError):
            lookup_rules(self.db, "1203-008541", result["batch_id"])

    def test_query_is_read_only_and_does_not_create_missing_database(self):
        with self.assertRaises(sqlite3.OperationalError):
            lookup_rules(self.db, "03438806", 1)
        self.assertFalse(self.db.exists())
        self.write_book([example_row()])
        result = import_workbook(self.source, self.db, self.config)
        before = self.db.read_bytes()
        lookup_rules(self.db, "03438806", result["batch_id"])
        self.assertEqual(before, self.db.read_bytes())

    def test_empty_input_or_bad_header_leaves_no_schema_or_import(self):
        for rows, headers in [([], HEADERS), ([example_row()], ["wrong"] + HEADERS[1:])]:
            with self.subTest(headers=headers[0]):
                self.write_book(rows, headers)
                with self.assertRaises(ValueError):
                    import_workbook(self.source, self.db, self.config)
                with closing(sqlite3.connect(self.db)) as connection:
                    self.assertEqual([], connection.execute("SELECT name FROM sqlite_master").fetchall())

    def test_unrelated_database_and_unsupported_version_are_not_modified(self):
        self.write_book([example_row()])
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("CREATE TABLE unrelated(value TEXT)")
            connection.commit()
        before = self.db.read_bytes()
        with self.assertRaises(ValueError):
            import_workbook(self.source, self.db, self.config)
        self.assertEqual(before, self.db.read_bytes())
        self.db.unlink()
        result = import_workbook(self.source, self.db, self.config)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("PRAGMA user_version = 999")
        with self.assertRaises(ValueError):
            import_workbook(self.source, self.db, self.config)
        with self.assertRaises(ValueError):
            lookup_rules(self.db, "03438806", result["batch_id"])

    def test_sqlite_integer_overflow_rolls_back(self):
        row = example_row()
        row[0] = str(2**63)
        self.write_book([example_row(), row])
        with self.assertRaisesRegex(ValueError, "정수 범위"):
            import_workbook(self.source, self.db, self.config)
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual([], connection.execute("SELECT name FROM sqlite_master").fetchall())

    def test_cli_import_query_and_rejected_import_report(self):
        self.write_book([example_row()])
        report = self.root / "import.json"
        output = self.root / "query.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, import_main([str(self.source), "--db", str(self.db), "--report", str(report)]))
            self.assertEqual(0, query_main([str(self.db), "--batch-id", "1", "--sec-code", "03438806", "--output", str(output)]))
            self.assertEqual(3, query_main([str(self.db), "--batch-id", "1", "--sec-code", "99999999", "--output", str(output)]))
        self.assertEqual("NOT_FOUND", json.loads(output.read_text(encoding="utf-8"))["match_status"])
        bad = example_row()
        bad[2] = None
        self.write_book([bad])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(2, import_main([str(self.source), "--db", str(self.db), "--report", str(report)]))
        self.assertEqual("rejected", json.loads(report.read_text(encoding="utf-8"))["status"])
        self.assertEqual((1, 1), self.counts())

    def test_cli_path_collisions_preserve_source_mapping_and_db(self):
        self.write_book([example_row()])
        original = self.source.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, import_main([str(self.source), "--db", str(self.source)]))
            self.assertEqual(2, import_main([str(self.source), "--db", str(self.db), "--report", str(self.source)]))
            self.assertEqual(2, import_main([str(self.source), "--db", str(self.mapping)]))
        self.assertEqual(original, self.source.read_bytes())
        self.assertFalse(self.db.exists())
        imported = import_workbook(self.source, self.db, self.config)
        before = self.db.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, query_main([str(self.db), "--batch-id", str(imported["batch_id"]),
                                           "--sec-code", "03438806", "--output", str(self.db)]))
        self.assertEqual(before, self.db.read_bytes())


if __name__ == "__main__":
    unittest.main()
