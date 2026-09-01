"""PyUnit tests for the room rent lookup. No model is involved, by design.

The lookup exists because the judge misread this table: on B05 it reported
800/day where the row grants a room category, inventing a breach that the
second pass then spread across three more lines. Room rent gates the
proportionate deduction, so one wrong figure here is worth four wrong lines -
which is why it is now a table read rather than a question.
"""

import unittest

from core.agent import room_limit
from core.models import BillLine, PolicySchedule
from core.room_limit import lookup, primary_room_clause, room_rank, table_lookup


class TableLookupTest(unittest.TestCase):
    def test_every_rupee_row_star_health_states(self):
        for sum_insured, expected in (
            (100000, 2000.0),
            (200000, 2000.0),
            (300000, 5000.0),
            (400000, 5000.0),
        ):
            entitlement = lookup("star_health", sum_insured)
            self.assertEqual(entitlement.per_day, expected, sum_insured)
            self.assertEqual(entitlement.clause_id, "II.1")

    def test_the_category_rows_state_no_rupee_figure(self):
        for sum_insured in (500000, 1000000, 1500000, 2000000, 2500000):
            entitlement = lookup("star_health", sum_insured)
            self.assertIsNone(entitlement.per_day, sum_insured)
            self.assertEqual(entitlement.category, "Single Standard A/C Room")

    def test_a_sum_insured_with_no_row_falls_through_to_the_judge(self):
        # Interpolating between rows would invent a figure the policy does not
        # state, which is the failure this replaces.
        self.assertIsNone(lookup("star_health", 750000))

    def test_a_plan_comparison_table_is_not_a_room_table(self):
        # hdfc_ergo E.1.4 is keyed on sum insured too, and reading a room limit
        # out of its AYUSH row is exactly the kind of confident nonsense this
        # module exists to stop.
        self.assertIsNone(table_lookup("hdfc_ergo", 1000000))


class WordingLookupTest(unittest.TestCase):
    def test_hdfc_states_at_actuals(self):
        entitlement = lookup("hdfc_ergo", 1000000)
        self.assertTrue(entitlement.at_actuals)
        self.assertEqual(entitlement.clause_id, "B.1.1")

    def test_niva_defers_to_the_schedule_with_no_fallback(self):
        entitlement = lookup("niva_bupa", 2500000)
        self.assertTrue(entitlement.defers_to_schedule)
        self.assertEqual(entitlement.clause_id, "6.2.4")
        self.assertIsNone(entitlement.per_day)

    def test_the_clause_cited_is_the_one_that_grants_the_room(self):
        self.assertEqual(primary_room_clause("star_health").clause_id, "II.1")
        self.assertEqual(primary_room_clause("hdfc_ergo").clause_id, "B.1.1")
        self.assertEqual(primary_room_clause("niva_bupa").clause_id, "6.2.4")


class ScheduleTest(unittest.TestCase):
    def test_a_schedule_figure_wins(self):
        entitlement = lookup("hdfc_ergo", 300000, PolicySchedule(room_limit_per_day=5000))
        self.assertEqual(entitlement.per_day, 5000.0)
        self.assertEqual(entitlement.clause_id, "B.1.1")

    def test_a_blank_schedule_changes_nothing(self):
        self.assertTrue(lookup("niva_bupa", 500000, PolicySchedule()).defers_to_schedule)


class RoomRankTest(unittest.TestCase):
    def test_the_ladder_is_ordered(self):
        ranks = [
            room_rank(x)
            for x in ("shared", "single standard a/c", "single private", "deluxe", "suite")
        ]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(ranks, [1, 2, 3, 4, 5])

    def test_an_unnamed_room_has_no_rank(self):
        self.assertIsNone(room_rank("room rent"))


def state(item, amount, qty, policy, sum_insured, schedule=None):
    return {
        "line": BillLine(item=item, amount=amount, qty=qty),
        "policy": policy,
        "sum_insured": sum_insured,
        "schedule": schedule,
        "rule_type": "room_rent",
        "trace": [],
    }


class AgentNodeTest(unittest.TestCase):
    """The node settles the line without a judge call, or says it could not."""

    def test_a_breach_is_computed_from_the_table_row(self):
        result = room_limit(
            state("Room Rent (Single A/C) 8,000 x 5 days", 40000, 5, "star_health", 300000)
        )
        verdict = result["verdict"]
        self.assertEqual(verdict.allowed, 25000.0)
        self.assertEqual(verdict.limit_per_day, 5000.0)
        self.assertTrue(verdict.over_limit)
        self.assertEqual(verdict.clause_id, "II.1")

    def test_a_room_within_a_category_entitlement_is_paid_in_full(self):
        # B05: shared room, 10,00,000 sum insured. The judge read 800/day here.
        result = room_limit(
            state("Room Rent (Shared) 4,000 x 3 days", 12000, 3, "star_health", 1000000)
        )
        verdict = result["verdict"]
        self.assertEqual(verdict.allowed, 12000.0)
        self.assertFalse(verdict.over_limit)
        self.assertFalse(verdict.needs_human)

    def test_a_room_above_a_category_entitlement_is_flagged_not_guessed(self):
        result = room_limit(
            state("Room Rent (Suite) 20,000 x 2 days", 40000, 2, "star_health", 1000000)
        )
        verdict = result["verdict"]
        self.assertIsNone(verdict.allowed)
        self.assertTrue(verdict.needs_human)

    def test_at_actuals_pays_the_room_in_full(self):
        result = room_limit(
            state("Room Rent (Single A/C) 6,000 x 2 days", 12000, 2, "hdfc_ergo", 500000)
        )
        self.assertEqual(result["verdict"].allowed, 12000.0)
        self.assertEqual(result["verdict"].clause_id, "B.1.1")

    def test_a_missing_schedule_abstains_rather_than_defaulting(self):
        result = room_limit(
            state("Room Rent (Single Private) 6,000 x 2 days", 12000, 2, "niva_bupa", 500000)
        )
        verdict = result["verdict"]
        self.assertIsNone(verdict.allowed)
        self.assertTrue(verdict.needs_human)
        self.assertIn("policy schedule", verdict.reason)

    def test_no_matching_row_falls_back_to_the_judge_and_says_so(self):
        result = room_limit(state("Room Rent 6,000 x 2 days", 12000, 2, "star_health", 750000))
        self.assertIsNone(result.get("verdict"))
        note = result["trace"][-1]
        self.assertEqual(note["node"], "room_limit")
        self.assertFalse(note["resolved"])
        self.assertEqual(note["fallback"], "judge")

    def test_a_line_that_is_not_room_rent_is_left_alone(self):
        s = state("Surgeon Fee", 80000, 1, "star_health", 300000)
        s["rule_type"] = "other"
        self.assertIsNone(room_limit(s).get("verdict"))


if __name__ == "__main__":
    unittest.main()
