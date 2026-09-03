"""The pasteable bills, and the check that they describe the same bill.

Every eval bill is stored twice - a `lines` array the eval scores against, and
a `bill_text` the UI and `core.bill` read. Nothing else in the repo compares
them, so a fixture whose text says 8,000 and whose lines say 9,000 would score
perfectly on the JSON path and be wrong everywhere a human looks.

These tests are deterministic and call no model.
"""

import json
import unittest
from pathlib import Path

from eval.make_text_bills import TEXT_DIR, compare, load_bills, parse_text_bill

BILLS_DIR = Path(__file__).parent.parent / "eval" / "bills"


class TextAndJsonAgreeTest(unittest.TestCase):
    """The whole fixture set, checked in one pass."""

    @classmethod
    def setUpClass(cls):
        cls.bills = load_bills()

    def test_there_are_44_bills(self):
        self.assertEqual(len(self.bills), 44)

    def test_every_bill_text_matches_its_lines(self):
        for bill in self.bills:
            with self.subTest(bill=bill["bill_id"]):
                problems, _ = compare(bill)
                self.assertEqual(problems, [], f"{bill['bill_id']}: {problems}")

    def test_a_truncated_description_is_a_warning_not_a_failure(self):
        """Three bills print a description cut off at the column width.

        The audit turns on the amounts, and real printed bills truncate, so
        this is reported rather than failed - but it is still reported.
        """
        truncated = [b["bill_id"] for b in self.bills if compare(b)[1]]
        self.assertEqual(truncated, ["B13", "B21", "B39"])


class RowReaderTest(unittest.TestCase):
    """The regex that reads a printed bill back."""

    def test_a_description_containing_digits_still_splits_correctly(self):
        rows, _ = parse_text_bill("Room Rent (Single A/C) 8,000 x 5 days           5    40,000.00")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item"], "Room Rent (Single A/C) 8,000 x 5 days")
        self.assertEqual(rows[0]["qty"], 5)
        self.assertEqual(rows[0]["amount"], 40000.0)

    def test_the_grand_total_is_read_as_a_total_not_an_item(self):
        rows, total = parse_text_bill(
            "Surgeon Fee                                     1    80,000.00\n"
            "GRAND TOTAL                                         236,000.00"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(total, 236000.0)

    def test_a_wrong_amount_in_the_text_is_a_problem(self):
        bill = {
            "bill_id": "X",
            "bill_text": (
                "Surgeon Fee                                     1    80,000.00\n"
                "GRAND TOTAL                                          80,000.00"
            ),
            "lines": [{"item": "Surgeon Fee", "amount": 90000.0, "qty": 1}],
            "total_charged": 90000.0,
        }
        problems, warnings = compare(bill)
        self.assertEqual(warnings, [])
        self.assertEqual(len(problems), 2)  # the line, and the total

    def test_a_missing_line_in_the_text_is_a_problem(self):
        bill = {
            "bill_id": "X",
            "bill_text": "Surgeon Fee                                     1    80,000.00",
            "lines": [
                {"item": "Surgeon Fee", "amount": 80000.0, "qty": 1},
                {"item": "Anaesthetist Charges", "amount": 15000.0, "qty": 1},
            ],
            "total_charged": 95000.0,
        }
        problems, _ = compare(bill)
        self.assertIn("the text has 1 items, the JSON has 2", problems[0])


class GeneratedFilesTest(unittest.TestCase):
    """What the script wrote is what the JSON holds.

    Skipped rather than failed when the directory is absent: the files are a
    generated convenience, and `make_text_bills.py` regenerates them.
    """

    def setUp(self):
        if not TEXT_DIR.exists():
            self.skipTest("run eval/make_text_bills.py first")

    def test_one_text_file_per_bill(self):
        written = sorted(p.stem for p in TEXT_DIR.glob("*.txt"))
        expected = sorted(json.loads(p.read_text())["bill_id"] for p in BILLS_DIR.glob("*.json"))
        self.assertEqual(written, expected)

    def test_each_file_is_the_bill_text_verbatim(self):
        for path in sorted(BILLS_DIR.glob("*.json")):
            bill = json.loads(path.read_text())
            with self.subTest(bill=bill["bill_id"]):
                written = (TEXT_DIR / f"{bill['bill_id']}.txt").read_text()
                self.assertEqual(written.rstrip(), bill["bill_text"].rstrip())

    def test_the_index_lists_every_bill(self):
        index = (TEXT_DIR / "INDEX.md").read_text()
        for path in sorted(BILLS_DIR.glob("*.json")):
            bill_id = json.loads(path.read_text())["bill_id"]
            with self.subTest(bill=bill_id):
                self.assertIn(f"| {bill_id} |", index)


if __name__ == "__main__":
    unittest.main()
