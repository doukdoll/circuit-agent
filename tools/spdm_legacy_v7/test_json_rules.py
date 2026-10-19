"""Synthetic analysis fixtures; standard library only, never company input."""

from contextlib import closing, redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from import_rules import main as import_main
from inspect_json_rules import main as inspect_main
from json_rules import parse_analysis
from query_rules import main as query_main
from setup_rules import default_output_dir, run_setup
from sqlite_store import (InspectionError, SCHEMA_VERSION,
                          import_analysis, lookup_rules, validate_sec_code)
from verify_environment import verify


def synthetic_record(sec="00112233", uid="synthetic:1", checks=2):
    return {
        "checkpoint_id": "synthetic-checkpoint", "row_uid": uid, "sec_code": sec, "status": "normalized",
        "analysis": {"summary": "가상 전원 연결 및 길이 조건", "issues": [], "checks": [
            {"applicability": "each synthetic supply", "evidence": [{"field": "checkpoint", "quote": "synthetic evidence"}],
             "level": "mandatory", "parameters": [
                 {"name": "synthetic numeric", "qualifier": None, "role": "expected", "unit": "uF", "value": 0.1},
                 {"name": "synthetic formula", "qualifier": "<", "role": "limit", "unit": "V", "value": "0.5*TEST_V"}],
             "required_design_facts": ["synthetic capacitor value", "synthetic trace length"],
             "requirement": "가상 기준을 만족해야 함", "requirement_id": f"{uid}:R{index + 1}",
             "sec_code": sec, "target_description": "TEST supply pair", "target_kind": "power_pin"}
            for index in range(checks)]}
    }


class JSONRulesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="SPDM 검증 ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "가상 규칙.json"
        self.db = self.root / "rules.sqlite"

    def write(self, records):
        self.source.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    def counts(self):
        with closing(sqlite3.connect(self.db)) as connection:
            return tuple(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                         for name in ("checkpoints", "rules"))

    def test_parent_checks_and_structures_roundtrip_without_observed_values(self):
        records = [synthetic_record(checks=12), synthetic_record("1234-567890", "synthetic:2", 1)]
        records[0]["analysis"]["issues"] = [{"code": "ambiguous", "description": "synthetic ambiguity"}]
        self.write(records)
        original = self.source.read_bytes()
        result = import_analysis(self.source, self.db, preview_limit=1)
        self.assertEqual(13, result["stored_rows"])
        self.assertEqual(1, len(result["inspection"]["preview"]))
        self.assertEqual((2, 13), self.counts())
        rules = lookup_rules(self.db, "00112233")["rules"]
        self.assertEqual(12, len(rules))
        first = rules[0]
        self.assertEqual(records[0]["analysis"]["checks"][0], first["raw"])
        self.assertEqual(0.1, first["parameters"][0]["value"])
        self.assertEqual("0.5*TEST_V", first["parameters"][1]["value"])
        self.assertIsNone(first["parameters"][0]["qualifier"])
        self.assertIsNone(first["design_value"])
        self.assertIsNone(first["original_checkpoint"])
        self.assertEqual(first["required_design_facts"], first["display_fields"]["설계치"])
        self.assertEqual(first["summary"], first["display_fields"]["checkPoint"])
        self.assertEqual(first["requirement"], first["specification"])
        self.assertEqual("/0/analysis/checks/0", first["source_json_pointer"])
        self.assertTrue(first["has_preprocessing_issues"])
        self.assertEqual("ambiguous", first["checkpoint_issues"][0]["code"])
        self.assertEqual("MATCHED", lookup_rules(self.db, "1234-567890")["match_status"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(records[0], json.loads(connection.execute(
                "SELECT raw_json FROM checkpoints ORDER BY id LIMIT 1").fetchone()[0]))
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
        self.assertEqual(original, self.source.read_bytes())

    def test_utf8_bom_reimport_and_changed_values_replace_current_rules(self):
        record = synthetic_record()
        self.source.write_text(json.dumps([record]), encoding="utf-8-sig")
        first = import_analysis(self.source, self.db)
        self.assertEqual("imported", first["status"])
        second = import_analysis(self.source, self.db, preview_limit=0)
        self.assertEqual("replaced", second["status"])
        self.assertEqual([], second["inspection"]["preview"])
        self.assertEqual((1, 2), self.counts())
        record["analysis"]["checks"][0]["parameters"][0]["value"] = 0
        self.write([record])
        third = import_analysis(self.source, self.db)
        self.assertEqual("replaced", third["status"])
        self.assertEqual((1, 2), self.counts())
        self.assertEqual(0, lookup_rules(self.db, "00112233")["rules"][0]["parameters"][0]["value"])

    def test_add_change_delete_and_removed_sec_keep_only_latest_input(self):
        self.write([synthetic_record(checks=35)])
        import_analysis(self.source, self.db)
        self.assertEqual((1, 35), self.counts())
        record = synthetic_record(checks=36)
        self.write([record])
        import_analysis(self.source, self.db)
        self.assertEqual((1, 36), self.counts())
        record["analysis"]["checks"][0]["requirement"] = "변경된 최신 규격"
        self.write([record])
        import_analysis(self.source, self.db)
        self.assertEqual((1, 36), self.counts())
        self.assertEqual("변경된 최신 규격", lookup_rules(self.db, "00112233")["rules"][0]["specification"])
        self.write([synthetic_record("1234-567890", "synthetic:2", 1)])
        import_analysis(self.source, self.db)
        self.assertEqual((1, 1), self.counts())
        self.assertEqual("NOT_FOUND", lookup_rules(self.db, "00112233")["match_status"])
        self.assertEqual(1, len(lookup_rules(self.db, "1234-567890")["rules"]))

    def test_repeated_import_does_not_accumulate_rows_tables_or_pages(self):
        self.write([synthetic_record(checks=36)])
        import_analysis(self.source, self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            initial_pages = connection.execute("PRAGMA page_count").fetchone()[0]
        for _ in range(25):
            import_analysis(self.source, self.db)
        self.assertEqual((1, 36), self.counts())
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(initial_pages, connection.execute("PRAGMA page_count").fetchone()[0])
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            self.assertEqual({"checkpoints", "rules"}, tables)
            for table in tables:
                columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                self.assertNotIn("batch_id", columns)

    def test_fixed_fields_types_sec_and_inner_outer_consistency_are_validated(self):
        cases = []
        r = synthetic_record(); del r["analysis"]["checks"][0]["requirement"]; cases.append(r)
        r = synthetic_record(); r["analysis"]["checks"][0]["requirements"] = "wrong key"; cases.append(r)
        r = synthetic_record(); r["analysis"]["checks"][0]["required_design_facts"] = "not a list"; cases.append(r)
        r = synthetic_record(); r["analysis"]["checks"][0]["sec_code"] = "99998888"; cases.append(r)
        r = synthetic_record(); r["sec_code"] = 112233; cases.append(r)
        r = synthetic_record(); r["analysis"]["checks"][0]["parameters"][0]["value"] = float("inf"); cases.append(r)
        for record in cases:
            with self.subTest(record=cases.index(record)):
                self.write([record])
                self.assertGreater(parse_analysis(self.source).report["errors"], 0)
                with self.assertRaises(InspectionError):
                    import_analysis(self.source, self.db)
        self.assertFalse(self.db.exists())

    def test_duplicate_object_keys_nonfinite_numbers_and_bad_root_rejected(self):
        for text in ('{"a":1,"a":2}', '[NaN]', '[1e999]', '{}', '[]', '{broken'):
            with self.subTest(text=text):
                self.source.write_text(text, encoding="utf-8")
                self.assertGreater(parse_analysis(self.source).report["errors"], 0)

    def test_empty_or_null_analysis_preserves_checkpoint_and_returns_no_checks(self):
        first = synthetic_record(checks=0)
        second = synthetic_record("1234-567890", "synthetic:2")
        second["analysis"] = None
        second["status"] = "pending"
        self.write([first, second])
        result = import_analysis(self.source, self.db)
        self.assertEqual(0, result["stored_rows"])
        self.assertEqual((2, 0), self.counts())
        matched = lookup_rules(self.db, "00112233")
        self.assertEqual("NO_CHECKS", matched["match_status"])
        self.assertEqual(1, len(matched["checkpoints"]))
        self.assertEqual("NOT_FOUND", lookup_rules(self.db, "99998888")["match_status"])

    def test_new_target_values_parameter_types_and_duplicates_preserved(self):
        record = synthetic_record()
        check = record["analysis"]["checks"][0]
        check["target_kind"] = "future_target_kind"
        check["parameters"][0]["value"] = [False, 0, {"minimum": 1, "maximum": 3}]
        check["parameters"][0]["unit"] = None
        record["analysis"]["checks"][1] = deepcopy(check)
        self.write([record])
        result = import_analysis(self.source, self.db)
        self.assertEqual(1, len(result["inspection"]["duplicate_candidates"]))
        rules = lookup_rules(self.db, "00112233")["rules"]
        self.assertEqual(2, len(rules))
        self.assertEqual([False, 0, {"minimum": 1, "maximum": 3}], rules[0]["parameters"][0]["value"])
        self.assertEqual(1, rules[1]["duplicate_first_row"])

    def test_invalid_new_source_does_not_change_existing_database(self):
        self.write([synthetic_record()])
        import_analysis(self.source, self.db)
        before = self.db.read_bytes()
        record = synthetic_record()
        record["analysis"]["checks"][0]["evidence"] = "bad"
        self.write([record])
        with self.assertRaises(InspectionError):
            import_analysis(self.source, self.db)
        self.assertEqual(before, self.db.read_bytes())

    def test_sql_error_rolls_back_both_checkpoints_and_checks(self):
        self.write([synthetic_record()])
        import_analysis(self.source, self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("""CREATE TRIGGER fail_json_rule BEFORE INSERT ON rules
                WHEN NEW.specification='explode' BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END""")
            connection.commit()
        before = lookup_rules(self.db, "00112233")
        record = synthetic_record()
        record["analysis"]["summary"] = "실패한 변경"
        record["analysis"]["checks"][0]["requirement"] = "먼저 삽입된 변경"
        record["analysis"]["checks"][1]["requirement"] = "explode"
        self.write([record])
        with self.assertRaises(sqlite3.IntegrityError):
            import_analysis(self.source, self.db)
        self.assertEqual((1, 2), self.counts())
        self.assertEqual(before, lookup_rules(self.db, "00112233"))

    def test_unsupported_versions_and_foreign_database_are_unchanged(self):
        self.write([synthetic_record()])
        for version in (1, 2, 3, 4, 5, 6, 999):
            with self.subTest(version=version):
                self.db.unlink(missing_ok=True)
                result = import_analysis(self.source, self.db)
                with closing(sqlite3.connect(self.db)) as connection:
                    connection.execute(f"PRAGMA user_version={version}")
                before = self.db.read_bytes()
                with self.assertRaises(ValueError):
                    import_analysis(self.source, self.db)
                with self.assertRaises(ValueError):
                    lookup_rules(self.db, "00112233")
                self.assertEqual(before, self.db.read_bytes())
        self.db.unlink()
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("CREATE TABLE unrelated_business_data(value INTEGER)")
            connection.commit()
        before = self.db.read_bytes()
        with self.assertRaises(ValueError):
            import_analysis(self.source, self.db)
        self.assertEqual(before, self.db.read_bytes())

    def test_query_is_read_only_and_missing_database_is_not_created(self):
        with self.assertRaises(sqlite3.OperationalError):
            lookup_rules(self.db, "00112233")
        self.assertFalse(self.db.exists())
        self.write([synthetic_record()])
        result = import_analysis(self.source, self.db)
        before = self.db.read_bytes()
        lookup_rules(self.db, "00112233")
        self.assertEqual(before, self.db.read_bytes())
        with self.assertRaises(ValueError):
            lookup_rules(self.db, "   ")

    def test_flexible_sec_formats_are_preserved_and_not_merged(self):
        codes = ["00112233", "0012345678", "1234-567890", "1234567890", "AbC-9", "abc-9", " X-1 "]
        records = [synthetic_record(sec, f"synthetic:{index}", 1) for index, sec in enumerate(codes)]
        self.write(records)
        self.assertEqual(0, parse_analysis(self.source).report["errors"])
        import_analysis(self.source, self.db)
        for record in records:
            code = record["sec_code"]
            with self.subTest(sec=code):
                result = lookup_rules(self.db, code)
                self.assertEqual(code, result["sec_code"])
                self.assertEqual([record["analysis"]["checks"][0]], [r["raw"] for r in result["rules"]])
                self.assertEqual(code, validate_sec_code(code))
        self.assertEqual("NOT_FOUND", lookup_rules(self.db, "X-1")["match_status"])

    def test_blank_null_and_numeric_sec_are_rejected_before_replacement(self):
        self.write([synthetic_record()])
        import_analysis(self.source, self.db)
        before = self.db.read_bytes()
        for code in ("", "   ", "\t\n", None, 1234567890, True):
            with self.subTest(sec=code):
                self.write([synthetic_record(code)])
                with self.assertRaises(InspectionError):
                    import_analysis(self.source, self.db)
                with self.assertRaises(ValueError):
                    validate_sec_code(code)
                self.assertEqual(before, self.db.read_bytes())

    def test_both_tables_reject_empty_sec_via_sql_constraint(self):
        self.write([synthetic_record("0012345678")])
        import_analysis(self.source, self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            for table in ("checkpoints", "rules"):
                for code in ("", "   "):
                    with self.subTest(table=table, sec=code):
                        with self.assertRaises(sqlite3.IntegrityError):
                            connection.execute(f"UPDATE {table} SET sec_code=?", (code,))
                        connection.rollback()

    def test_missing_parent_cannot_be_linked(self):
        self.write([synthetic_record()])
        import_analysis(self.source, self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE rules SET checkpoint_db_id=999999")
            connection.rollback()
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())

    def test_replacement_does_not_reuse_committed_ids_and_relinks_parents(self):
        records = [synthetic_record(), synthetic_record("another-sec", "synthetic:2", 1)]
        self.write(records)
        import_analysis(self.source, self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            old_max = {table: connection.execute(f"SELECT MAX(id) FROM {table}").fetchone()[0]
                       for table in ("checkpoints", "rules")}
        import_analysis(self.source, self.db)
        self.assertEqual((2, 3), self.counts())
        with closing(sqlite3.connect(self.db)) as connection:
            for table in ("checkpoints", "rules"):
                with self.subTest(table=table):
                    new_min = connection.execute(f"SELECT MIN(id) FROM {table}").fetchone()[0]
                    self.assertGreater(new_min, old_max[table])
                    maximum = connection.execute(f"SELECT MAX(id) FROM {table}").fetchone()[0]
                    sequence = connection.execute("SELECT seq FROM sqlite_sequence WHERE name=?", (table,)).fetchone()[0]
                    self.assertEqual(maximum, sequence)
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
        for record in records:
            result = lookup_rules(self.db, record["sec_code"])
            self.assertEqual(record["analysis"]["checks"], [rule["raw"] for rule in result["rules"]])
            parent_id = result["checkpoints"][0]["id"]
            self.assertTrue(all(rule["checkpoint_db_id"] == parent_id for rule in result["rules"]))

    def test_whole_pipeline_runs_when_network_connections_are_disabled(self):
        self.write([synthetic_record()])
        with patch("socket.socket.connect", side_effect=AssertionError("network is disabled")), patch(
            "socket.create_connection", side_effect=AssertionError("network is disabled")
        ):
            result = import_analysis(self.source, self.db)
            query = lookup_rules(self.db, "00112233")
        self.assertEqual(2, len(query["rules"]))

    def test_json_cli_inspect_import_query_and_collisions(self):
        self.write([synthetic_record()])
        report = self.root / "inspection.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, inspect_main([str(self.source), "--report", str(report)]))
            self.assertEqual(0, import_main([str(self.source), "--db", str(self.db), "--report", str(report)]))
            self.assertEqual(0, query_main([str(self.db), "--sec-code", "00112233", "--output", str(report)]))
        self.assertEqual(2, len(json.loads(report.read_text(encoding="utf-8"))["rules"]))
        original = self.source.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, import_main([str(self.source), "--db", str(self.source)]))
            self.assertEqual(2, inspect_main([str(self.source), "--report", str(self.source)]))
        self.assertEqual(original, self.source.read_bytes())
        record = synthetic_record()
        del record["analysis"]["summary"]
        self.write([record])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(2, import_main([str(self.source), "--db", str(self.db), "--report", str(report)]))
        self.assertEqual("rejected", json.loads(report.read_text(encoding="utf-8"))["status"])

    def verify_without_nested_unit_suite(self):
        actual_run = subprocess.run

        def run(argv, **kwargs):
            if "unittest" in argv:
                return subprocess.CompletedProcess(argv, 0, "", "Synthetic suite already run")
            return actual_run(argv, **kwargs)

        with patch("verify_environment.subprocess.run", side_effect=run):
            return verify(self.source)

    def test_environment_preserves_input_error_details_without_rule_previews(self):
        record = synthetic_record()
        record["analysis"]["checks"][0]["sec_code"] = "different-code"
        self.write([record])
        before = self.source.read_bytes()
        result = self.verify_without_nested_unit_suite()
        self.assertEqual("failed", result["status"])
        failure = result["failed_step"]
        self.assertEqual("inspect_json_rules.py", failure["command"])
        self.assertEqual(2, failure["returncode"])
        self.assertTrue(failure["stdout"])
        self.assertEqual("", failure["stderr"])
        self.assertEqual("/0/analysis/checks/0/sec_code", failure["inspection"]["issues"][0]["path"])
        self.assertIn("SEC가 다름", result["error"])
        self.assertNotIn("preview", failure["inspection"])
        self.assertEqual(before, self.source.read_bytes())

    def test_environment_inspects_malformed_and_missing_field_inputs_first(self):
        for contents in ('{broken', '[{"sec_code":"test"}]', '[{"a":1,"a":2}]'):
            with self.subTest(contents=contents):
                self.source.write_text(contents, encoding="utf-8")
                result = self.verify_without_nested_unit_suite()
                self.assertEqual("failed", result["status"])
                self.assertGreater(result["failed_step"]["inspection"]["errors"], 0)
                self.assertTrue(result["failed_step"]["inspection"]["issues"])

    def test_environment_preserves_stderr_when_no_diagnostic_report_exists(self):
        self.write([synthetic_record()])

        def run(argv, **kwargs):
            if "unittest" in argv:
                return subprocess.CompletedProcess(argv, 0, "", "Synthetic suite already run")
            return subprocess.CompletedProcess(argv, 2, "", "synthetic permission denied")

        with patch("verify_environment.subprocess.run", side_effect=run):
            result = verify(self.source)
        self.assertEqual("synthetic permission denied", result["failed_step"]["stderr"])
        self.assertIn("synthetic permission denied", result["error"])

    def test_null_applicability_remains_null_and_is_flagged_for_review(self):
        record = synthetic_record()
        record["analysis"]["checks"][0]["applicability"] = None
        self.write([record])
        parsed = parse_analysis(self.source)
        self.assertEqual(0, parsed.report["errors"])
        import_analysis(self.source, self.db)
        rule = lookup_rules(self.db, record["sec_code"])["rules"][0]
        self.assertIsNone(rule["applicability"])
        self.assertIsNone(rule["raw"]["applicability"])
        self.assertTrue(rule["has_preprocessing_issues"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertIsNone(connection.execute("SELECT applicability FROM rules ORDER BY id LIMIT 1").fetchone()[0])

    def test_optional_source_error_is_preserved_and_visible_without_checks(self):
        for error in (None, "synthetic analysis failure", {"message": "synthetic", "retryable": True}):
            with self.subTest(error=error):
                record = synthetic_record(checks=0)
                record["analysis"] = None
                record["status"] = "error"
                record["error"] = error
                self.write([record])
                import_analysis(self.source, self.db)
                result = lookup_rules(self.db, record["sec_code"])
                self.assertEqual("NO_CHECKS", result["match_status"])
                checkpoint = result["checkpoints"][0]
                self.assertTrue(checkpoint["has_source_error_field"])
                self.assertEqual(error, checkpoint["source_error"])
                self.assertTrue(checkpoint["has_preprocessing_issues"])
                with closing(sqlite3.connect(self.db)) as connection:
                    self.assertEqual(record, json.loads(connection.execute("SELECT raw_json FROM checkpoints").fetchone()[0]))

    def test_source_error_with_checks_is_visible_and_unknown_fields_still_rejected(self):
        record = synthetic_record()
        record["error"] = "synthetic analysis failure"
        self.write([record])
        import_analysis(self.source, self.db)
        result = lookup_rules(self.db, record["sec_code"])
        self.assertEqual(record["error"], result["rules"][0]["source_error"])
        self.assertTrue(result["rules"][0]["has_preprocessing_issues"])
        record["unexpected_field"] = "not allowed"
        self.write([record])
        with self.assertRaises(InspectionError):
            import_analysis(self.source, self.db)

    def gui(self):
        dialogs, messages = Mock(), Mock()
        dialogs.askopenfilename.return_value = str(self.source)
        dialogs.asksaveasfilename.return_value = str(self.db)
        messages.askyesno.return_value = True
        return dialogs, messages

    def test_gui_imports_bom_json_and_reports_counts_using_existing_schema(self):
        record = synthetic_record()
        record["analysis"]["checks"][0]["applicability"] = None
        self.source.write_text(json.dumps([record], ensure_ascii=False), encoding="utf-8-sig")
        original = self.source.read_bytes()
        dialogs, messages = self.gui()
        self.assertEqual(0, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual((1, 2), self.counts())
        self.assertIn("체크포인트: 1개", messages.showinfo.call_args.args[1])
        self.assertIn("세부 규칙: 2개", messages.showinfo.call_args.args[1])
        self.assertIn(str(self.db), messages.showinfo.call_args.args[1])
        self.assertIsNone(lookup_rules(self.db, record["sec_code"])["rules"][0]["applicability"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(7, connection.execute("PRAGMA user_version").fetchone()[0])
            for table in ("checkpoints", "rules"):
                ddl = connection.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0]
                self.assertIn("AUTOINCREMENT", ddl)
        self.assertEqual(original, self.source.read_bytes())
        self.assertEqual(1, len(list(self.root.glob("rules_import_*.json"))))
        messages.askyesno.assert_not_called()
        messages.showerror.assert_not_called()
        self.assertEqual(self.root / "local-output", default_output_dir(self.root / "app" / "spdm_json"))

    def test_gui_confirmed_replacement_keeps_only_latest_and_uses_new_ids(self):
        self.write([synthetic_record(checks=3)])
        import_analysis(self.source, self.db)
        old_id = lookup_rules(self.db, "00112233")["rules"][-1]["id"]
        self.write([synthetic_record(checks=1)])
        dialogs, messages = self.gui()
        self.assertEqual(0, run_setup(dialogs, messages, app_dir=self.root))
        messages.askyesno.assert_called_once()
        self.assertEqual("no", messages.askyesno.call_args.kwargs["default"])
        self.assertEqual((1, 1), self.counts())
        self.assertGreater(lookup_rules(self.db, "00112233")["rules"][0]["id"], old_id)

    def test_gui_cancel_input_does_not_create_any_files(self):
        dialogs, messages = self.gui()
        dialogs.askopenfilename.return_value = ""
        self.assertEqual(0, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual([], list(self.root.iterdir()))
        dialogs.asksaveasfilename.assert_not_called()
        messages.showinfo.assert_not_called()

    def test_gui_cancel_output_does_not_import(self):
        self.write([synthetic_record()])
        dialogs, messages = self.gui()
        dialogs.asksaveasfilename.return_value = ""
        self.assertEqual(0, run_setup(dialogs, messages, app_dir=self.root))
        self.assertFalse(self.db.exists())
        self.assertEqual([], list(self.root.glob("*_import_*.json")))
        messages.showinfo.assert_not_called()

    def test_gui_declined_replacement_leaves_existing_db_unchanged(self):
        self.write([synthetic_record()])
        import_analysis(self.source, self.db)
        before = self.db.read_bytes()
        dialogs, messages = self.gui()
        messages.askyesno.return_value = False
        self.assertEqual(0, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual([], list(self.root.glob("*_import_*.json")))
        messages.showinfo.assert_not_called()

    def test_gui_invalid_json_shows_path_and_preserves_existing_db(self):
        self.write([synthetic_record()])
        import_analysis(self.source, self.db)
        before = self.db.read_bytes()
        record = synthetic_record()
        del record["analysis"]["checks"][0]["requirement"]
        self.write([record])
        dialogs, messages = self.gui()
        self.assertEqual(2, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual(before, self.db.read_bytes())
        self.assertIn("/0/analysis/checks/0/requirement", messages.showerror.call_args.args[1])
        report = json.loads(next(self.root.glob("*_import_*.json")).read_text(encoding="utf-8"))
        self.assertEqual("rejected", report["status"])
        messages.showinfo.assert_not_called()

    def test_gui_old_schema_is_rejected_without_changing_existing_db(self):
        self.write([synthetic_record()])
        import_analysis(self.source, self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("PRAGMA user_version=6")
        before = self.db.read_bytes()
        dialogs, messages = self.gui()
        self.assertEqual(2, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual(before, self.db.read_bytes())
        self.assertIn("지원하지 않는 DB 버전", messages.showerror.call_args.args[1])
        messages.showinfo.assert_not_called()

    def test_gui_rejects_source_database_collision_without_changing_input(self):
        self.write([synthetic_record()])
        original = self.source.read_bytes()
        dialogs, messages = self.gui()
        dialogs.asksaveasfilename.return_value = str(self.source)
        self.assertEqual(2, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual(original, self.source.read_bytes())
        self.assertIn("경로는 서로 달라야", messages.showerror.call_args.args[1])

    def test_gui_report_failure_does_not_claim_committed_import_was_rolled_back(self):
        self.write([synthetic_record()])
        dialogs, messages = self.gui()
        actual_write = Path.write_text

        def write(path, *args, **kwargs):
            if "_import_" in path.name:
                raise PermissionError("synthetic report permission denied")
            return actual_write(path, *args, **kwargs)

        with patch.object(Path, "write_text", write):
            self.assertEqual(2, run_setup(dialogs, messages, app_dir=self.root))
        self.assertEqual((1, 2), self.counts())
        self.assertIn("DB 적재 완료", messages.showwarning.call_args.args[0])
        messages.showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
