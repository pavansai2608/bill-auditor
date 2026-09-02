"""The two deterministic bill readers must agree with the fixtures and each other.

Three things read a bill in this repo and only one of them is the parser:

* `core.bill.parse_bill` - the model, on the server. The only count that
  decides an audit. It is checked against the fixtures by
  `eval/make_text_bills.py --llm`, which costs 44 model calls and so cannot
  live here.
* `eval.make_text_bills.parse_text_bill` - a regex over the fixture's fixed
  column layout, so the `bill_text` and `lines` halves of a fixture cannot
  drift apart unnoticed.
* `frontend/src/lib/billStats.ts` - the reading shown under the paste box
  while the user types, so pasting a bill answers "did it understand me?"
  before the audit runs.

The last two implement the same rule in two languages, which is how they
drifted the first time: the browser reader dropped B27's "Total Knee
Replacement - Surgeon Fee" (Rs 1,45,000, the largest line on that bill)
because the line begins with a word that also begins a total, and it ignored
plain integers like "Surgical Gloves   1200" because they are not punctuated
like money. Neither bug could reach a recorded eval number - `eval/evaluate.py`
builds its `BillLine`s straight from the JSON `lines` array and parses no text
at all - but a wrong count under the user's bill teaches them not to trust the
figures further down the page.

So both readers run over all 44 fixtures here, and disagreeing with the JSON or
with each other fails the build.
"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from eval.make_text_bills import parse_text_bill

ROOT = Path(__file__).resolve().parents[1]
BILLS_DIR = ROOT / "eval" / "bills"
BILL_STATS = ROOT / "frontend" / "src" / "lib" / "billStats.ts"

# Everything the scripts below need arrives in the environment. Passing it
# after `-e` does not work: node reads a trailing positional as another module
# to load and fails resolving the bill text as a path.
PREAMBLE = (
    "import { pathToFileURL } from 'node:url';\n"
    "const { readBill } = await import(pathToFileURL(process.env.BA_STATS).href);\n"
)

READ_ALL_FIXTURES = PREAMBLE + (
    "import { readdirSync, readFileSync } from 'node:fs';\n"
    "const dir = process.env.BA_BILLS;\n"
    "const out = {};\n"
    "for (const name of readdirSync(dir).filter((f) => f.endsWith('.json')).sort()) {\n"
    "  const bill = JSON.parse(readFileSync(`${dir}/${name}`, 'utf8'));\n"
    "  out[bill.bill_id] = readBill(bill.bill_text);\n"
    "}\n"
    "process.stdout.write(JSON.stringify(out));\n"
)

READ_ONE_TEXT = PREAMBLE + "process.stdout.write(JSON.stringify(readBill(process.env.BA_TEXT)));\n"

# The only node failure worth skipping over. Anything else is a broken reader
# or a broken test, and skipping those is how a silent bug survives a green run.
CANNOT_STRIP_TYPES = ("erasablesyntaxonly", "experimental-strip-types", "unknown file extension")


def run_node(script: str, **env: str) -> dict:
    """Evaluate `script` under node and parse what it printed.

    Node strips the TypeScript itself. It does so by default from 23 onward and
    behind a flag before that, so the flagged form is the fallback rather than
    the first thing tried - passing a removed flag to a newer node is itself an
    error.
    """
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node is not installed, so the browser reader cannot be run")

    environment = {**os.environ, "BA_STATS": str(BILL_STATS), **env}
    failure = ""
    for command in ([node], [node, "--experimental-strip-types"]):
        finished = subprocess.run(
            [*command, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            env=environment,
        )
        if finished.returncode == 0:
            return json.loads(finished.stdout)
        failure = finished.stderr.strip()

    if any(marker in failure.lower() for marker in CANNOT_STRIP_TYPES):
        raise unittest.SkipTest(f"this node cannot read TypeScript: {failure}")
    raise AssertionError(f"node could not run {BILL_STATS.name}:\n{failure}")


def read_bills() -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(BILLS_DIR.glob("*.json"))]


class BothReadersAgreeWithTheFixturesTest(unittest.TestCase):
    """Item counts and totals, three ways, over all 44 bills."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bills = read_bills()
        cls.browser = run_node(READ_ALL_FIXTURES, BA_BILLS=str(BILLS_DIR))

    def test_there_are_44_bills(self) -> None:
        self.assertEqual(44, len(self.bills))

    def test_the_browser_reader_saw_every_bill(self) -> None:
        self.assertEqual(sorted(bill["bill_id"] for bill in self.bills), sorted(self.browser))

    def test_item_counts_agree(self) -> None:
        """The JSON is the truth; both readers have to arrive at it."""
        disagreements = []
        for bill in self.bills:
            bill_id = bill["bill_id"]
            expected = len(bill["lines"])
            rows, _ = parse_text_bill(bill["bill_text"])
            browser = self.browser[bill_id]["items"]
            if len(rows) != expected or browser != expected:
                disagreements.append(
                    f"{bill_id}: JSON has {expected} lines, "
                    f"the regex reader found {len(rows)}, "
                    f"the browser reader found {browser}"
                )
        self.assertEqual([], disagreements, "\n".join(["the readers disagree:", *disagreements]))

    def test_totals_agree(self) -> None:
        """A count can match while a dropped line is swapped for a total."""
        disagreements = []
        for bill in self.bills:
            bill_id = bill["bill_id"]
            expected = sum(line["amount"] for line in bill["lines"])
            rows, _ = parse_text_bill(bill["bill_text"])
            regex_total = sum(row["amount"] for row in rows)
            browser_total = self.browser[bill_id]["total"]
            if abs(regex_total - expected) > 0.01 or abs(browser_total - expected) > 0.01:
                disagreements.append(
                    f"{bill_id}: JSON totals {expected:,.2f}, "
                    f"the regex reader {regex_total:,.2f}, "
                    f"the browser reader {browser_total:,.2f}"
                )
        self.assertEqual([], disagreements, "\n".join(["the totals disagree:", *disagreements]))

    def test_b27_keeps_its_surgeon_fee(self) -> None:
        """The regression by name, because it was the largest line on the bill."""
        b27 = next(bill for bill in self.bills if bill["bill_id"] == "B27")
        self.assertIn(
            "Total Knee Replacement - Surgeon Fee",
            b27["bill_text"],
            "this test is pointless if the fixture no longer holds the line it guards",
        )
        self.assertEqual(len(b27["lines"]), self.browser["B27"]["items"])
        self.assertEqual(145000, max(line["amount"] for line in b27["lines"]))


class TheBrowserReaderIsShyInTheRightPlacesTest(unittest.TestCase):
    """The two bugs it had, and the address that made the second one subtle."""

    def read(self, text: str) -> dict:
        return run_node(READ_ONE_TEXT, BA_TEXT=text)

    def test_a_charge_may_begin_with_the_word_total(self) -> None:
        stats = self.read("Total Knee Replacement - Surgeon Fee            1   145,000.00\n")
        self.assertEqual(1, stats["items"])
        self.assertEqual(145000, stats["total"])

    def test_a_line_that_is_only_a_total_is_not_a_charge(self) -> None:
        for label in ("GRAND TOTAL", "Total", "Sub-total", "Net Payable"):
            with self.subTest(label=label):
                self.assertEqual(0, self.read(f"{label}   339,500.00\n")["items"])

    def test_a_plain_integer_in_its_own_column_is_money(self) -> None:
        stats = self.read("Surgical Gloves   1200\n")
        self.assertEqual(1, stats["items"])
        self.assertEqual(1200, stats["total"])

    def test_a_postcode_is_not_money(self) -> None:
        """One space, not two - which is the whole difference from the line above."""
        self.assertEqual(0, self.read("Chennai - 600 034\n")["items"])


if __name__ == "__main__":
    unittest.main()
