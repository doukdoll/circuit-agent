"""Synthetic inputs only: no company workbook or network is needed."""

from copy import deepcopy
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
import tempfile
import unittest

from openpyxl import Workbook
from openpyxl.utils.datetime import CALENDAR_MAC_1904, CALENDAR_WINDOWS_1900, from_excel

from inspect_rules import inspect_workbook, main, normalize, read_mapping


HEADERS = ["adminno", "seqno", "sec_code", "writer", "comp_date", "maker", "maker_pn",
           "adminno", "seqno", "Checkpoint", "Specification", "설계치", "참조문서", "input_5",
           "savefolder", "ref_date", "category", "pin_info", "ldrc_check_tp", "ldrc_regist_tp",
           "ldrc_check_date", "ldrc_checker", "ldrc_id"]


def example_row():
    return [100, 8, "03438806", 999, 41092.10496, " TEST ", "SYNTHETIC",
            100, 0, "  EN|KO\r\n최소 10 kΩ ±5%  ", "≤ 5 V", "0", '@첨부파일 "test.pdf"',
            999, "0L", 41092, "a", "24, A1", "N", None, None, None, None]


class InspectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic.xlsx"
        self.config = read_mapping(Path(__file__).with_name("mapping.json"))

    def write_book(self, rows, headers=None, epoch=None):
        book = Workbook()
        book.active.title = "병합결과"
        if epoch:
            book.epoch = epoch
        book.active.append(headers or HEADERS)
        for row in rows:
            book.active.append(row)
        book.save(self.source)
        book.close()

    def test_duplicate_headers_leading_zero_units_and_input_immutability(self):
        self.write_book([example_row()])
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        report = inspect_workbook(self.source, self.config)
        item = report["preview"][0]
        self.assertEqual(0, report["errors"])
        self.assertEqual("03438806", item["selected"]["sec_code"])
        self.assertEqual(8, item["selected"]["part_seqno"])
        self.assertEqual(0, item["selected"]["rule_seqno"])
        self.assertEqual("EN|KO\n최소 10 kΩ ±5%", item["selected"]["checkpoint"])
        self.assertEqual("  EN|KO\r\n최소 10 kΩ ±5%  ", item["raw"]["checkpoint"])
        self.assertEqual("0", item["selected"]["design_value"])
        self.assertEqual("24, A1", item["selected"]["pin_info"])
        self.assertEqual(before, hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_blank_checkpoint_is_retained_and_empty_rows_are_counted(self):
        row = example_row()
        row[9] = " \n "
        second = example_row()
        second[8] = 1
        self.write_book([row, [None] * 23, second])
        report = inspect_workbook(self.source, self.config)
        self.assertEqual(2, report["data_rows"])
        self.assertEqual(1, report["empty_rows"])
        self.assertIsNone(report["preview"][0]["selected"]["checkpoint"])
        self.assertEqual(4, report["preview"][1]["source_row"])
        self.assertEqual(0, report["errors"])

    def test_numeric_sec_is_flagged_without_padding(self):
        row = example_row()
        row[2] = 3438806
        self.write_book([row])
        report = inspect_workbook(self.source, self.config)
        self.assertEqual(1, report["errors"])
        self.assertEqual(3438806, report["preview"][0]["raw"]["sec_code"])
        self.assertIsNone(report["preview"][0]["selected"]["sec_code"])

    def test_conflicting_duplicates_are_reported_not_removed(self):
        second = example_row()
        second[9] = "다른 규칙 내용"
        self.write_book([example_row(), second])
        report = inspect_workbook(self.source, self.config)
        self.assertEqual(2, report["data_rows"])
        self.assertEqual([{"row": 3, "first_row": 2}], report["duplicate_candidates"])
        self.assertEqual("다른 규칙 내용", report["preview"][1]["selected"]["checkpoint"])

    def test_cleaned_column_selection_is_explicit_without_fallback(self):
        config = deepcopy(self.config)
        checkpoint = next(f for f in config["fields"] if f["name"] == "checkpoint")
        del checkpoint["column"]
        checkpoint["header"] = "Checkpoint_cleaned"
        self.write_book([example_row() + ["정제된 조건"], example_row() + [None]],
                        HEADERS + ["Checkpoint_cleaned"])
        report = inspect_workbook(self.source, config)
        self.assertEqual("정제된 조건", report["preview"][0]["selected"]["checkpoint"])
        self.assertIsNone(report["preview"][1]["selected"]["checkpoint"])

    def test_shifted_or_ambiguous_headers_fail_before_processing(self):
        self.write_book([example_row()], ["unexpected"] + HEADERS[1:])
        with self.assertRaises(ValueError):
            inspect_workbook(self.source, self.config)
        self.write_book([example_row()])
        config = deepcopy(self.config)
        del config["fields"][0]["column"]
        with self.assertRaisesRegex(ValueError, "중복"):
            inspect_workbook(self.source, config)

    def test_dates_use_workbook_epoch_and_keep_time(self):
        config = deepcopy(self.config)
        config["fields"].append({"name": "comp_date", "column": "E", "header": "comp_date", "type": "datetime"})
        serial = example_row()[4]
        for epoch in [CALENDAR_WINDOWS_1900, CALENDAR_MAC_1904]:
            with self.subTest(epoch=epoch):
                self.write_book([example_row()], epoch=epoch)
                result = inspect_workbook(self.source, config)["preview"][0]["selected"]["comp_date"]
                self.assertEqual(from_excel(serial, epoch).isoformat(), result)
                self.assertNotEqual("00:00:00", result.split("T")[1])
        self.assertEqual("2026-10-14T12:30:00", normalize(datetime(2026, 10, 14, 12, 30), "datetime", CALENDAR_WINDOWS_1900))

    def test_formula_error_invalid_integer_and_unknown_category(self):
        row = example_row()
        row[1] = 1.5
        row[9] = '=CONCAT("TEST", "RULE")'
        row[10] = "#VALUE!"
        row[16] = "z"
        self.write_book([row])
        report = inspect_workbook(self.source, self.config)
        self.assertEqual(3, report["errors"])
        self.assertEqual(1, report["warnings"])
        self.assertEqual("z", report["preview"][0]["selected"]["category"])

    def test_preview_limit_does_not_limit_validation(self):
        bad = example_row()
        bad[2] = None
        self.write_book([example_row(), bad])
        report = inspect_workbook(self.source, self.config, preview_limit=0)
        self.assertEqual([], report["preview"])
        self.assertEqual(2, report["data_rows"])
        self.assertEqual(1, report["errors"])

    def test_cli_writes_utf8_report_and_returns_error_status(self):
        self.write_book([example_row()])
        report_path = self.root / "output" / "report.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, main([str(self.source), "--report", str(report_path)]))
        self.assertEqual(1, json.loads(report_path.read_text(encoding="utf-8"))["data_rows"])
        row = example_row()
        row[2] = None
        self.write_book([row])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(2, main([str(self.source), "--report", str(report_path)]))
        self.assertTrue(report_path.exists())

    def test_cli_rejects_overwriting_input_and_handles_non_xlsx(self):
        self.write_book([example_row()])
        before = self.source.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, main([str(self.source), "--report", str(self.source)]))
        self.assertEqual(before, self.source.read_bytes())
        self.source.write_bytes(b"not an xlsx workbook")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, main([str(self.source), "--report", str(self.root / "report.json")]))


if __name__ == "__main__":
    unittest.main()
