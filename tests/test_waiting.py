"""PyUnit tests for waiting periods. Two dates and a number, no model.

The rule this pins hardest is the one that failed on B03: the judge applied a
24-month specified-disease exclusion to an admission 61 months into the policy
and zeroed a payable line. It was confident and it cited a real clause. Dates
settle this, so dates decide it.
"""

import unittest
from datetime import date

from core.audit import audit_lines
from core.models import BillLine
from core.waiting import (
    assess,
    confirmed_condition,
    is_waiting_clause,
    months_between,
    periods,
)


class DateArithmeticTest(unittest.TestCase):
    def test_whole_months_only(self):
        self.assertEqual(months_between(date(2025, 10, 1), date(2026, 2, 14)), 4)

    def test_a_part_month_has_not_been_served(self):
        self.assertEqual(months_between(date(2025, 10, 15), date(2026, 10, 14)), 11)

    def test_the_anniversary_counts(self):
        self.assertEqual(months_between(date(2024, 1, 1), date(2026, 1, 1)), 24)


class PeriodsTest(unittest.TestCase):
    def test_each_policy_states_all_three_periods(self):
        for policy, expected in (
            ("star_health", {"ped": "III.1", "specified": "III.2", "initial": "III.3"}),
            # hdfc_ergo carries all three codes in one clause.
            ("hdfc_ergo", {"ped": "C.1", "specified": "C.1", "initial": "C.1"}),
            ("niva_bupa", {"ped": "5.1.1", "specified": "5.1.2", "initial": "5.1.3"}),
        ):
            found = {p.kind: p.clause_id for p in periods(policy)}
            self.assertEqual(found, expected, policy)

    def test_the_periods_are_read_from_the_clause_not_hardcoded(self):
        by_kind = {p.kind: p for p in periods("niva_bupa")}
        self.assertEqual(by_kind["ped"].months, 36)
        self.assertEqual(by_kind["specified"].months, 24)
        self.assertEqual(by_kind["initial"].days, 30)

    def test_waiting_clauses_are_recognised(self):
        self.assertTrue(is_waiting_clause("niva_bupa", "5.1.2"))
        self.assertFalse(is_waiting_clause("niva_bupa", "6.2.4"))


class SpecifiedDiseaseTest(unittest.TestCase):
    def test_inside_the_period_the_whole_admission_is_excluded(self):
        verdict = assess(
            ["Hernia Repair - Surgeon Fee", "Room Rent (Shared) 3,500 x 2 days"],
            "hdfc_ergo",
            "2025-10-01",
            "2026-02-14",
        )
        self.assertTrue(verdict.excluded)
        self.assertEqual(verdict.clause_id, "C.1")
        self.assertIn("4 months", verdict.reason)

    def test_past_the_period_nothing_is_excluded(self):
        # B03: cataract, 61 months of coverage, a 24-month period.
        verdict = assess(
            ["Cataract Surgery - Right Eye Package"], "niva_bupa", "2020-11-20", "2026-01-14"
        )
        self.assertFalse(verdict.excluded)
        self.assertIn("61 months", verdict.note)

    def test_a_condition_the_policy_does_not_list_is_not_acted_on(self):
        # star_health III.2 ends at "f. List of specific diseases/procedures;"
        # and the list is not in the extracted text. Zeroing a bill against a
        # list this system cannot read would be a guess.
        condition, period = confirmed_condition("star_health", ["Cataract Surgery"])
        self.assertIsNone(condition)
        self.assertIsNotNone(period)
        self.assertFalse(
            assess(["Cataract Surgery"], "star_health", "2025-10-01", "2026-01-01").excluded
        )


class ThirtyDayTest(unittest.TestCase):
    def test_an_admission_inside_thirty_days_is_excluded(self):
        verdict = assess(["Fever - Ward Charges"], "niva_bupa", "2026-01-01", "2026-01-20")
        self.assertTrue(verdict.excluded)
        self.assertEqual(verdict.kind, "initial")
        self.assertIn("19 days", verdict.reason)

    def test_an_accident_is_carved_out(self):
        verdict = assess(
            ["Fracture Fixation - Road Accident"], "niva_bupa", "2026-01-01", "2026-01-20"
        )
        self.assertFalse(verdict.excluded)
        self.assertIn("accident", verdict.note)

    def test_after_thirty_days_it_does_not_apply(self):
        self.assertFalse(assess(["Fever"], "niva_bupa", "2026-01-01", "2026-03-01").excluded)


class PedTest(unittest.TestCase):
    def test_ped_is_recorded_but_never_applied(self):
        verdict = assess(["Angioplasty"], "star_health", "2025-10-01", "2026-01-01")
        self.assertFalse(verdict.excluded)
        self.assertIn("pre-existing", verdict.note)
        self.assertIn("36 months", verdict.note)


class MissingDatesTest(unittest.TestCase):
    def test_without_dates_nothing_is_assumed(self):
        verdict = assess(["Hernia Repair"], "hdfc_ergo", None, None)
        self.assertFalse(verdict.excluded)
        self.assertIn("not assessed", verdict.note)


class AuditIntegrationTest(unittest.TestCase):
    """The bill-level short circuit: no search, no judge, every line nil."""

    def test_a_bill_inside_a_waiting_period_needs_no_model(self):
        lines = [
            BillLine(item="Hernia Repair - Surgeon Fee", amount=45000, qty=1),
            BillLine(item="Room Rent (Shared) 3,500 x 2 days", amount=7000, qty=2),
            BillLine(item="Medicines and Drugs", amount=4200, qty=1),
        ]
        report = audit_lines(
            lines,
            "hdfc_ergo",
            500000,
            policy_start_date="2025-10-01",
            admission_date="2026-02-14",
        )
        self.assertEqual(report.total_allowed, 0.0)
        self.assertEqual(report.flagged_count, 0)
        for verdict in report.lines:
            self.assertEqual(verdict.allowed, 0.0)
            self.assertEqual(verdict.clause_id, "C.1")
        note = next(e for e in report.trace if e.get("node") == "waiting")
        self.assertTrue(note["excluded"])


if __name__ == "__main__":
    unittest.main()
