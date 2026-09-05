"""The report the static site ships must be a real one, and must stay real.

`frontend/src/data/exampleReport.json` is the only output a visitor to
https://pavansai2608.github.io/bill-auditor/ can see, because Pages serves
files and the audit needs a clause index and a model. It is exported from an
eval checkpoint by `eval/export_example_report.py` and never written by hand.

That makes it the one report nobody re-runs, which is exactly the kind of file
that rots quietly. Two properties are pinned here, both chosen because their
failure would be invisible on the page:

* **Every clause it cites exists.** A fabricated citation is the worst failure
  this system can produce and the eval tracks it as a metric that must stay at
  zero. A committed JSON file is not covered by that metric, so it is covered
  here - against `data/clauses.json` itself, not against a list copied out of
  it.
* **The arithmetic adds up.** The page splits the bill into payable, deducted
  and flagged and draws a bar from the three. If the totals do not reconcile
  with the lines, the bar is wrong and the figures beside it are wrong, and
  nothing else in the repository would notice.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "frontend" / "src" / "data" / "exampleReport.json"
CLAUSES = ROOT / "data" / "clauses.json"
NON_PAYABLE = ROOT / "data" / "non_payable.json"

# The non-payable list is IRDAI's, not an insurer's, so it has no clause in the
# policy index. `core/audit.py` cites it under this id and the eval scores it as
# a real citation; see the withdrawn first v2 row in eval/results.md, which
# counted 18 of these as fabrications.
IRDAI_ID = "IRDAI-List-I"


class ExampleReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundled = json.loads(BUNDLED.read_text())
        cls.report = cls.bundled["report"]
        clauses = json.loads(CLAUSES.read_text())
        cls.ids = {(c["policy"], c["clause_id"]) for c in clauses}

    def test_it_exists_and_names_where_it_came_from(self):
        recorded = self.bundled["recorded"]
        for field in ("run", "bill_id", "recorded_at", "backend", "model"):
            self.assertTrue(recorded.get(field), f"provenance is missing {field}")

    def test_the_non_payable_list_is_still_the_source_of_that_id(self):
        """If the list moves, the id this report cites stops meaning anything."""
        self.assertTrue(NON_PAYABLE.exists(), f"{NON_PAYABLE} is missing")

    def test_every_cited_clause_exists_in_the_index(self):
        policy = self.report["policy"]
        for line in self.report["lines"]:
            clause_id = line["clause_id"]
            if clause_id is None or clause_id == IRDAI_ID:
                continue
            self.assertIn(
                (policy, clause_id),
                self.ids,
                f"{line['item']!r} cites {policy} {clause_id}, which is not in the index",
            )

    def test_a_line_with_a_clause_has_a_figure_and_one_without_has_none(self):
        for line in self.report["lines"]:
            if line["needs_human"]:
                self.assertIsNone(line["allowed"], f"{line['item']!r} is flagged but has a figure")
            else:
                self.assertIsNotNone(
                    line["allowed"], f"{line['item']!r} is not flagged but has no figure"
                )
                self.assertIsNotNone(
                    line["clause_id"], f"{line['item']!r} was decided without citing anything"
                )

    def test_the_totals_reconcile_with_the_lines(self):
        charged = sum(line["charged"] for line in self.report["lines"])
        allowed = sum(line["allowed"] or 0 for line in self.report["lines"])
        self.assertAlmostEqual(charged, self.report["total_charged"], places=2)
        self.assertAlmostEqual(allowed, self.report["total_allowed"], places=2)

    def test_the_flagged_count_is_the_number_of_flagged_lines(self):
        flagged = sum(1 for line in self.report["lines"] if line["needs_human"])
        self.assertEqual(flagged, self.report["flagged_count"])

    def test_nothing_is_allowed_more_than_it_was_charged(self):
        for line in self.report["lines"]:
            if line["allowed"] is not None:
                self.assertLessEqual(
                    line["allowed"], line["charged"], f"{line['item']!r} allows more than charged"
                )

    def test_the_assumptions_block_is_lifted_out_of_the_trace(self):
        """What api/shared.report_payload does; the UI reads its own field."""
        from_trace = [e for e in self.report["trace"] if e.get("assumption")]
        self.assertEqual(from_trace, self.report["assumptions"])

    def test_it_carries_no_patient_identifier(self):
        """The bill is masked before any prompt, so the report must be clean.

        A static site is public and permanent. This is the last gate before a
        name or a phone number would be committed and served for ever.
        """
        blob = json.dumps(self.bundled)
        for token in ("Ramesh", "9876543210", "B01500", "UHID"):
            self.assertNotIn(token, blob, f"{token} reached the published report")


if __name__ == "__main__":
    unittest.main()
