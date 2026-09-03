"""The example bill in the UI must be the eval fixture, not a copy of it.

`frontend/src/lib/exampleBill.ts` holds B01's text and its four form values so
the "Try it with an example" button can fill the whole form in one click. That
is a second copy of a fixture, and a second copy drifts: someone edits the JSON,
the button keeps loading last month's bill, and the one path a first-time
visitor takes is the one nobody re-checks.

So it is compared here rather than trusted. It is generated, never hand-edited.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "eval" / "bills" / "B01.json"
TEXT = ROOT / "eval" / "bills" / "text" / "B01.txt"
MODULE = ROOT / "frontend" / "src" / "lib" / "exampleBill.ts"


def field(source: str, name: str) -> str:
    """Read one `name: <json literal>,` out of the module."""
    match = re.search(rf"\b{name}:\s*(\"(?:[^\"\\]|\\.)*\"|\d+)", source, re.S)
    if match is None:
        raise AssertionError(f"exampleBill.ts has no {name}")
    raw = match.group(1)
    return json.loads(raw) if raw.startswith('"') else raw


class ExampleBillMatchesTheFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bill = json.loads(FIXTURE.read_text())
        cls.source = MODULE.read_text()

    def test_the_module_exists(self):
        self.assertTrue(MODULE.exists(), f"{MODULE} is missing; regenerate it")

    def test_it_is_bill_b01(self):
        self.assertEqual(field(self.source, "id"), self.bill["bill_id"])

    def test_the_text_is_the_fixture_verbatim(self):
        self.assertEqual(field(self.source, "text"), TEXT.read_text().rstrip())

    def test_the_form_values_match_the_fixture(self):
        self.assertEqual(field(self.source, "policy"), self.bill["policy"])
        self.assertEqual(int(field(self.source, "sumInsured")), int(self.bill["sum_insured"]))
        self.assertEqual(field(self.source, "policyStartDate"), self.bill["policy_start_date"])
        self.assertEqual(field(self.source, "admissionDate"), self.bill["admission_date"])

    def test_the_start_date_is_before_the_admission_date(self):
        """The form now rejects the reverse, so the example must not trip it."""
        self.assertLess(self.bill["policy_start_date"], self.bill["admission_date"])


if __name__ == "__main__":
    unittest.main()
