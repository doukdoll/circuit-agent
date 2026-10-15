"""Synthetic analysis fixtures; standard library only, never company input."""

from contextlib import closing, redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from import_rules import main as import_main
from inspect_json_rules import main as inspect_main
from json_rules import parse_analysis
from query_rules import main as query_main
from sqlite_store import (InspectionError, SCHEMA_VERSION,
                          import_analysis, lookup_rules)


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
                         for name in ("import_batches", "checkpoints", "rules"))

    def test_parent_checks_and_structures_roundtrip_without_observed_values(self):
        records = [synthetic_record(checks=12), synthetic_record("1234-567890", "synthetic:2", 1)]
        records[0]["analysis"]["issues"] = [{"code": "ambiguous", "description": "synthetic ambiguity"}]
        self.write(records)
        original = self.source.read_bytes()
        result = import_analysis(self.source, self.db, preview_limit=1)
        self.assertEqual(13, result["stored_rows"])
        self.assertEqual(1, len(result["inspection"]["preview"]))
        self.assertEqual((1, 2, 13), self.counts())
        rules = lookup_rules(self.db, "00112233", result["batch_id"])["rules"]
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
        self.assertEqual("MATCHED", lookup_rules(self.db, "1234-567890", result["batch_id"])["match_status"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(records[0], json.loads(connection.execute(
                "SELECT raw_json FROM checkpoints ORDER BY id LIMIT 1").fetchone()[0]))
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
        self.assertEqual(original, self.source.read_bytes())

    def test_utf8_bom_reimport_and_changed_values_make_new_snapshot(self):
        record = synthetic_record()
        self.source.write_text(json.dumps([record]), encoding="utf-8-sig")
        first = import_analysis(self.source, self.db)
        second = import_analysis(self.source, self.db, preview_limit=0)
        self.assertEqual("skipped", second["status"])
        self.assertEqual([], second["inspection"]["preview"])
        record["analysis"]["checks"][0]["parameters"][0]["value"] = 0
        self.write([record])
        third = import_analysis(self.source, self.db)
        self.assertNotEqual(first["batch_id"], third["batch_id"])
        self.assertEqual(0.1, lookup_rules(self.db, "00112233", first["batch_id"])["rules"][0]["parameters"][0]["value"])
        self.assertEqual(0, lookup_rules(self.db, "00112233", third["batch_id"])["rules"][0]["parameters"][0]["value"])

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
        self.assertEqual((1, 2, 0), self.counts())
        matched = lookup_rules(self.db, "00112233", result["batch_id"])
        self.assertEqual("NO_CHECKS", matched["match_status"])
        self.assertEqual(1, len(matched["checkpoints"]))
        self.assertEqual("NOT_FOUND", lookup_rules(self.db, "99998888", result["batch_id"])["match_status"])

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
        rules = lookup_rules(self.db, "00112233", result["batch_id"])["rules"]
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
        record = synthetic_record()
        record["analysis"]["checks"][1]["requirement"] = "explode"
        self.write([record])
        with self.assertRaises(sqlite3.IntegrityError):
            import_analysis(self.source, self.db)
        self.assertEqual((1, 1, 2), self.counts())

    def test_unsupported_versions_and_foreign_database_are_unchanged(self):
        self.write([synthetic_record()])
        for version in (1, 2, 999):
            with self.subTest(version=version):
                self.db.unlink(missing_ok=True)
                result = import_analysis(self.source, self.db)
                with closing(sqlite3.connect(self.db)) as connection:
                    connection.execute(f"PRAGMA user_version={version}")
                before = self.db.read_bytes()
                with self.assertRaises(ValueError):
                    import_analysis(self.source, self.db)
                with self.assertRaises(ValueError):
                    lookup_rules(self.db, "00112233", result["batch_id"])
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
            lookup_rules(self.db, "00112233", 1)
        self.assertFalse(self.db.exists())
        self.write([synthetic_record()])
        result = import_analysis(self.source, self.db)
        before = self.db.read_bytes()
        lookup_rules(self.db, "00112233", result["batch_id"])
        self.assertEqual(before, self.db.read_bytes())
        with self.assertRaises(ValueError):
            lookup_rules(self.db, "00112233", 999)
        with self.assertRaises(ValueError):
            lookup_rules(self.db, "00112233", True)

    def test_parent_from_another_snapshot_cannot_be_linked(self):
        self.write([synthetic_record()])
        first = import_analysis(self.source, self.db)
        changed = synthetic_record()
        changed["analysis"]["summary"] = "다음 버전"
        self.write([changed])
        second = import_analysis(self.source, self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            first_checkpoint = connection.execute("SELECT id FROM checkpoints WHERE batch_id=?", (first["batch_id"],)).fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE rules SET checkpoint_db_id=? WHERE batch_id=?", (first_checkpoint, second["batch_id"]))
            connection.rollback()
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())

    def test_whole_pipeline_runs_when_network_connections_are_disabled(self):
        self.write([synthetic_record()])
        with patch("socket.socket.connect", side_effect=AssertionError("network is disabled")), patch(
            "socket.create_connection", side_effect=AssertionError("network is disabled")
        ):
            result = import_analysis(self.source, self.db)
            query = lookup_rules(self.db, "00112233", result["batch_id"])
        self.assertEqual(2, len(query["rules"]))

    def test_json_cli_inspect_import_query_and_collisions(self):
        self.write([synthetic_record()])
        report = self.root / "inspection.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, inspect_main([str(self.source), "--report", str(report)]))
            self.assertEqual(0, import_main([str(self.source), "--db", str(self.db), "--report", str(report)]))
            self.assertEqual(0, query_main([str(self.db), "--batch-id", "1", "--sec-code", "00112233", "--output", str(report)]))
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


if __name__ == "__main__":
    unittest.main()
