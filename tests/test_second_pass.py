"""PyUnit tests for the second pass. Nothing here touches a model.

The pass exists because a per-line audit cannot see it: one room line billed
above its cap reduces the surgeon's fee, and nothing in the surgeon's-fee line
says so. What is tested hardest is the *scope* - the definition of Associated
Medical Expenses names what the deduction reaches and what it does not, and
rescaling an excluded line is a silent overcharge to the insured.
"""

import unittest

from core.assumptions import Assumptions
from core.models import BillLine, LineVerdict
from core.second_pass import (
    EXCLUDED,
    INCLUDED,
    UNNAMED,
    apply,
    breach_ratio,
    classify_for_ame,
    find_proportionate_clause,
)


def room(charged=40000.0, qty=5, limit=5000.0, over=True):
    """A room line billed at 8,000/day against a 5,000/day cap."""
    return (
        BillLine(item="room rent", amount=charged, qty=qty),
        LineVerdict(
            item="room rent",
            charged=charged,
            allowed=limit * qty,
            clause_id="II.1",
            reason="capped",
            over_limit=over,
            limit_per_day=limit,
        ),
    )


def other(item, charged=10000.0, allowed=None, needs_human=False):
    return (
        BillLine(item=item, amount=charged, qty=1),
        LineVerdict(
            item=item,
            charged=charged,
            allowed=charged if allowed is None else allowed,
            clause_id="II.1",
            reason="paid",
            needs_human=needs_human,
        ),
    )


def run(pairs, policy="star_health", assumptions=None):
    lines = [line for line, _ in pairs]
    verdicts = [verdict for _, verdict in pairs]
    return apply(lines, verdicts, policy, assumptions)


class ScopeTest(unittest.TestCase):
    """I.Def45 decides this, not a guess about what sounds medical."""

    def test_the_definition_names_these(self):
        for item in (
            "nursing charges",
            "operation theatre charges",
            "surgeon fee",
            "assistant surgeon",
            "anaesthetist charges",
            "consultant visit",
            "professional fees",
        ):
            self.assertEqual(classify_for_ame(item), INCLUDED, item)

    def test_the_definition_excludes_these(self):
        for item in (
            "medicines and drugs",
            "pharmacy",
            "consumables",
            "implant - titanium plate",
            "intraocular lens",
            "ct scan",
            "mri brain",
            "investigation charges",
            "icu charges",
            "ventilator support",
        ):
            self.assertEqual(classify_for_ame(item), EXCLUDED, item)

    def test_icu_nursing_is_an_icu_charge_not_a_nursing_charge(self):
        self.assertEqual(classify_for_ame("icu nursing charges"), EXCLUDED)

    def test_an_item_the_definition_does_not_name_is_unnamed(self):
        self.assertEqual(classify_for_ame("ambulance charges"), UNNAMED)
        self.assertEqual(classify_for_ame("registration charges"), UNNAMED)

    def test_the_room_line_itself_is_never_rescaled(self):
        self.assertEqual(classify_for_ame("room rent"), EXCLUDED)


class RatioTest(unittest.TestCase):
    def test_ratio_comes_from_the_per_day_rate_not_the_line_total(self):
        line, verdict = room()  # 40,000 over 5 days = 8,000/day against 5,000
        ratio, source = breach_ratio([line], [verdict])
        self.assertAlmostEqual(ratio, 0.625)
        self.assertEqual(source, "room rent")

    def test_no_breach_means_no_ratio(self):
        line, verdict = room(charged=20000.0, over=False)
        ratio, source = breach_ratio([line], [verdict])
        self.assertEqual(ratio, 1.0)
        self.assertIsNone(source)

    def test_the_lowest_ratio_wins_when_two_room_lines_breached(self):
        first = room()  # 0.625
        second = (
            BillLine(item="room rent - deluxe", amount=20000, qty=2),
            LineVerdict(
                item="room rent - deluxe",
                charged=20000,
                allowed=10000,
                clause_id="II.1",
                reason="capped",
                over_limit=True,
                limit_per_day=5000.0,
            ),
        )  # 10,000/day against 5,000 = 0.5
        ratio, _ = breach_ratio([first[0], second[0]], [first[1], second[1]])
        self.assertAlmostEqual(ratio, 0.5)


class ApplyTest(unittest.TestCase):
    def test_associated_expenses_are_rescaled_and_the_rest_are_not(self):
        pairs = [
            room(),
            other("surgeon fee", 100000.0),
            other("nursing charges", 20000.0),
            other("medicines and drugs", 15000.0),
            other("implant - titanium plate", 50000.0),
            other("ct scan", 8000.0),
            other("icu charges", 30000.0),
        ]
        verdicts, trace = run(pairs)
        by_item = {v.item: v for v in verdicts}

        self.assertEqual(by_item["surgeon fee"].allowed, 62500.0)
        self.assertEqual(by_item["nursing charges"].allowed, 12500.0)
        # Outside the definition: untouched, to the rupee.
        self.assertEqual(by_item["medicines and drugs"].allowed, 15000.0)
        self.assertEqual(by_item["implant - titanium plate"].allowed, 50000.0)
        self.assertEqual(by_item["ct scan"].allowed, 8000.0)
        self.assertEqual(by_item["icu charges"].allowed, 30000.0)
        # The room line keeps the amount its own cap produced.
        self.assertEqual(by_item["room rent"].allowed, 25000.0)
        self.assertTrue(trace[0]["applied"])
        self.assertAlmostEqual(trace[0]["ratio"], 0.625)

    def test_a_rescaled_line_cites_the_clause_that_authorises_it(self):
        verdicts, trace = run([room(), other("surgeon fee", 100000.0)])
        surgeon = verdicts[1]
        self.assertEqual(surgeon.clause_id, "II.1")
        self.assertIn("0.6250", surgeon.reason)
        self.assertEqual(trace[0]["clause_id"], "II.1")

    def test_nothing_happens_without_a_breach(self):
        pairs = [room(charged=20000.0, over=False), other("surgeon fee", 100000.0)]
        verdicts, trace = run(pairs)
        self.assertEqual(verdicts[1].allowed, 100000.0)
        self.assertFalse(trace[0]["applied"])

    def test_a_flagged_line_is_left_flagged(self):
        pairs = [room(), other("surgeon fee", 100000.0, allowed=None, needs_human=True)]
        pairs[1][1].allowed = None
        verdicts, _ = run(pairs)
        self.assertIsNone(verdicts[1].allowed)
        self.assertTrue(verdicts[1].needs_human)

    def test_no_deduction_when_differential_billing_is_ruled_out(self):
        pairs = [room(), other("surgeon fee", 100000.0)]
        verdicts, trace = run(pairs, assumptions=Assumptions(differential_billing=False))
        self.assertEqual(verdicts[1].allowed, 100000.0)
        self.assertFalse(trace[0]["applied"])
        self.assertIn("differential billing", trace[0]["why"])

    def test_every_untouched_line_says_why(self):
        pairs = [room(), other("medicines and drugs", 15000.0), other("ambulance charges", 2000.0)]
        _, trace = run(pairs)
        reasons = {e["item"]: e["why"] for e in trace if e.get("item")}
        self.assertIn("outside associated medical expenses", reasons["medicines and drugs"])
        self.assertIn("does not name this item", reasons["ambulance charges"])


class CitationTest(unittest.TestCase):
    """The cited clause has to exist in the index, or it is a fabrication."""

    def test_each_policy_resolves_to_a_real_operative_clause(self):
        from core.ingest import load_clauses

        clauses = load_clauses()
        for policy, expected in (
            ("star_health", "II.1"),
            ("hdfc_ergo", "B.1.1.1"),
            ("niva_bupa", "4.21"),
        ):
            clause = find_proportionate_clause(policy)
            self.assertIsNotNone(clause, policy)
            self.assertEqual(clause.clause_id, expected)
            self.assertIn(
                clause.clause_id, {c.clause_id for c in clauses if c.policy == policy}, policy
            )

    def test_the_definition_clause_is_not_the_one_cited(self):
        # star_health I.Def45 carries the phrase too, but it defines the term
        # rather than applying it.
        self.assertNotIn("Def", find_proportionate_clause("star_health").clause_id)


if __name__ == "__main__":
    unittest.main()
