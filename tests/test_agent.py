"""PyUnit tests for the agent loop.

The graph is exercised with the model and the retriever stubbed, so these test
the control flow - which is what has to hold whatever the model says on a
given run. The two rules that cost the most if they break are pinned here:
a confident answer is never re-asked, and a fabricated citation is never
reported.
"""

import unittest
from unittest import mock

from core.agent import (
    after_grade,
    audit_line,
    build_query,
    check_non_payable,
    classify,
)
from core.models import BillLine, Clause, JudgeOutput, Limit
from core.retrieve import RetrievedClause

POLICY = "star_health"
VALID = {"II.1", "II.8", "I.Def45"}


def clause(clause_id="II.1", text="Room rent is limited to Rs 5,000 per day."):
    return Clause(
        clause_id=clause_id,
        title="In-patient Treatment",
        text=text,
        page=9,
        policy=POLICY,
        rule_type="room_rent",
    )


def candidate(clause_id="II.1", score=0.95, text="Room rent is limited to Rs 5,000 per day."):
    c = clause(clause_id, text)
    return RetrievedClause(clause=c, score=score, matched_text=text)


def judged(clause_id="II.1", confident=True, limits=None):
    return JudgeOutput(
        clause_id=clause_id, limits=limits or [], confident=confident, reasoning="test"
    )


def run_line(item, amount, qty, outputs, candidates=None, sum_insured=300000):
    """Drive one line with a scripted sequence of judge outputs."""
    cands = [candidate()] if candidates is None else candidates
    seq = outputs if isinstance(outputs, list) else [outputs]
    with (
        mock.patch("core.agent.search", return_value=cands),
        mock.patch("core.agent.complete_structured", side_effect=seq * 5),
    ):
        return audit_line(BillLine(item=item, amount=amount, qty=qty), POLICY, sum_insured, VALID)


class FastPathTest(unittest.TestCase):
    def test_an_irdai_item_costs_no_search_and_no_model_call(self):
        with (
            mock.patch("core.agent.search") as searched,
            mock.patch("core.agent.complete_structured") as judged_call,
        ):
            verdict, trace = audit_line(
                BillLine(item="Surgical Gloves", amount=1200, qty=20), POLICY, 300000, VALID
            )
        searched.assert_not_called()
        judged_call.assert_not_called()
        self.assertEqual(verdict.allowed, 0.0)
        self.assertEqual(verdict.clause_id, "IRDAI-List-I")
        self.assertIn("#", verdict.reason)
        self.assertEqual(trace[-1]["judge_calls"], 0)
        self.assertTrue(trace[-1]["fast_path"])

    def test_ambulance_is_not_taken_by_the_list(self):
        """ "Ambulance" is IRDAI #67, but every policy has an ambulance benefit."""
        state = {"line": BillLine(item="Ambulance Charges", amount=1000, qty=1), "trace": []}
        check_non_payable(state)
        self.assertIsNone(state.get("verdict"))

    def test_an_ordinary_item_is_untouched(self):
        state = {"line": BillLine(item="Surgeon Fee", amount=80000, qty=1), "trace": []}
        check_non_payable(state)
        self.assertIsNone(state.get("verdict"))

    def test_the_ambulance_journey_is_left_to_the_benefit_clause(self):
        """List I #67 "Ambulance" names the equipment, not the journey.

        All three policies carry a named ambulance benefit - star_health II.8
        caps it at Rs 750 per hospitalization, hdfc_ergo covers it under
        B.1.1.1, niva_bupa under 6.2.4 - and the answer key pays all five
        ambulance lines in the set. The fast path must not zero them on a name
        match against the list.
        """
        for item in (
            "Ambulance",  # B21's item text, exactly
            "Ambulance Charges",
            "Road Ambulance",
            "AMBULANCE CHARGES",
        ):
            with self.subTest(item=item):
                state = {"line": BillLine(item=item, amount=1800, qty=1), "trace": []}
                check_non_payable(state)
                self.assertIsNone(state.get("verdict"), f"{item!r} was zeroed by the list")

    def test_ambulance_consumables_are_still_zeroed(self):
        """The other half, and the one a broad match breaks.

        The override used to be a regex run against the bill line before the
        list was searched, so anything containing "ambulance" skipped the fast
        path - including #49 "Ambulance Collar" and #50 "Ambulance Equipment",
        which are genuine List I consumables and must stay at zero. The
        override is now tested against the matched list ENTRY, so only the bare
        "Ambulance" entry defers to the benefit clause.
        """
        for item, expected_no in (
            ("Ambulance Collar", 49),
            ("Ambulance Equipment", 50),
            ("ambulance equipment charges", 50),
        ):
            with self.subTest(item=item):
                state = {"line": BillLine(item=item, amount=900, qty=1), "trace": []}
                check_non_payable(state)
                verdict = state.get("verdict")
                self.assertIsNotNone(verdict, f"{item!r} escaped the list")
                self.assertEqual(verdict.allowed, 0.0)
                self.assertEqual(verdict.clause_id, "IRDAI-List-I")
                self.assertIn(f"#{expected_no}", verdict.reason)


class RoutingTest(unittest.TestCase):
    def test_rule_types(self):
        for item, expected in [
            ("Room Rent (Single A/C) 8,000 x 5 days", "room_rent"),
            ("Cataract Surgery - Right Eye", "waiting_period"),
            ("Ambulance Charges", "sub_limit"),
            ("Surgeon Fee", "other"),
        ]:
            with self.subTest(item=item):
                state = {"line": BillLine(item=item, amount=100, qty=1), "trace": []}
                classify(state)
                self.assertEqual(state["rule_type"], expected)

    def test_each_attempt_asks_from_a_different_angle(self):
        """Re-asking a query that already missed is the one thing a retry must not do."""
        seen = set()
        for attempt in range(3):
            state = {
                "line": BillLine(item="Room Rent 8,000 x 5 days", amount=40000, qty=5),
                "rule_type": "room_rent",
                "attempts": attempt,
                "trace": [],
            }
            build_query(state)
            seen.add(state["query"])
        self.assertEqual(len(seen), 3)

    def test_the_query_drops_amounts_and_day_counts(self):
        state = {
            "line": BillLine(item="Room Rent (Deluxe) 11,000 x 5 days", amount=55000, qty=5),
            "rule_type": "other",
            "attempts": 0,
            "trace": [],
        }
        build_query(state)
        self.assertNotIn("11,000", state["query"])
        self.assertNotIn("5 days", state["query"])


class StoppingRuleTest(unittest.TestCase):
    def test_a_verdict_ends_the_loop(self):
        self.assertEqual(after_grade({"verdict": object()}), "done")

    def test_three_attempts_then_abstain(self):
        self.assertEqual(after_grade({"attempts": 3, "tool_calls": 6, "seen": []}), "abstain")

    def test_the_tool_call_cap_is_hard(self):
        self.assertEqual(after_grade({"attempts": 1, "tool_calls": 8, "seen": []}), "abstain")

    def test_two_identical_searches_stop_early(self):
        """A third identical round costs a judge call and tells us nothing new."""
        same = frozenset({"II.1", "II.20"})
        self.assertEqual(
            after_grade({"attempts": 1, "tool_calls": 4, "seen": [same, same]}), "abstain"
        )

    def test_different_searches_keep_going(self):
        self.assertEqual(
            after_grade(
                {"attempts": 1, "tool_calls": 4, "seen": [frozenset({"II.1"}), frozenset({"II.8"})]}
            ),
            "retry",
        )


class NeverRetryAConfidentAnswerTest(unittest.TestCase):
    """Constraint: retry only on an unconfident judge. Confident is final."""

    def test_a_confident_answer_is_accepted_on_the_first_attempt(self):
        verdict, trace = run_line(
            "Surgeon Fee",
            40000,
            5,
            judged(limits=[Limit(amount=5000, basis="per_day")]),
        )
        self.assertEqual(verdict.allowed, 25000)
        self.assertEqual(trace[-1]["judge_calls"], 1)
        self.assertEqual(trace[-1]["resolved_on_attempt"], 1)
        self.assertFalse(trace[-1]["retry_changed_answer"])

    def test_a_fabricated_citation_abstains_without_retrying(self):
        verdict, trace = run_line(
            "Surgeon Fee",
            80000,
            1,
            judged(clause_id="99.9", limits=[Limit(amount=1000, basis="absolute")]),
        )
        self.assertTrue(verdict.needs_human)
        self.assertIsNone(verdict.clause_id, "an invented citation must never be reported")
        self.assertEqual(trace[-1]["judge_calls"], 1, "a confident answer must not be re-asked")

    def test_an_unconfident_judge_is_retried(self):
        """Retrying is what an unconfident answer earns - up to the caps.

        Here the stub returns the same clauses every time, so the early-stop
        rule fires at attempt 2 rather than running the full three: a third
        identical round would cost a judge call and tell us nothing.
        """
        verdict, trace = run_line("Physiotherapy Sessions", 6000, 4, judged(confident=False))
        self.assertTrue(verdict.needs_human)
        self.assertEqual(trace[-1]["attempts"], 2)
        self.assertEqual(trace[-1]["judge_calls"], 2)
        self.assertIn("same clauses", verdict.reason)

    def test_three_attempts_when_the_search_keeps_moving(self):
        different = [
            [candidate("II.1")],
            [candidate("II.8")],
            [candidate("I.Def45")],
            [candidate("II.1")],
        ]
        with (
            mock.patch("core.agent.search", side_effect=different),
            mock.patch("core.agent.complete_structured", side_effect=[judged(confident=False)] * 5),
        ):
            verdict, trace = audit_line(
                BillLine(item="Physiotherapy Sessions", amount=6000, qty=4),
                POLICY,
                300000,
                VALID,
            )
        self.assertTrue(verdict.needs_human)
        self.assertEqual(trace[-1]["attempts"], 3)
        self.assertEqual(trace[-1]["judge_calls"], 3)

    def test_a_later_attempt_that_answers_is_recorded_as_such(self):
        outputs = [judged(confident=False), judged(limits=[Limit(amount=5000, basis="per_day")])]
        with (
            mock.patch("core.agent.search", return_value=[candidate()]),
            mock.patch("core.agent.complete_structured", side_effect=outputs),
        ):
            verdict, trace = audit_line(
                BillLine(item="Surgeon Fee", amount=40000, qty=5),
                POLICY,
                300000,
                VALID,
            )
        self.assertEqual(verdict.allowed, 25000)
        self.assertEqual(trace[-1]["resolved_on_attempt"], 2)
        self.assertTrue(trace[-1]["retry_changed_answer"], "the retry is what produced the answer")


class RoomRentSkipsTheJudgeTest(unittest.TestCase):
    """Path B: the room line is a table read, so the model is never asked.

    This is what the two fixtures above had to be changed for. It is also the
    change that took `clean` from 46.7% to 73.3%: the judge had been reporting
    800/day where the table grants a room category, and the second pass then
    spread that invented breach across three more lines.
    """

    def test_a_room_line_is_settled_without_a_model_call(self):
        with (
            mock.patch("core.agent.search", side_effect=AssertionError("must not retrieve")),
            mock.patch(
                "core.agent.complete_structured", side_effect=AssertionError("must not judge")
            ),
        ):
            verdict, trace = audit_line(
                BillLine(item="Room Rent (Single A/C) 8,000 x 5 days", amount=40000, qty=5),
                POLICY,
                300000,
                VALID,
            )
        self.assertEqual(verdict.allowed, 25000)
        self.assertEqual(verdict.limit_per_day, 5000)
        self.assertTrue(verdict.over_limit)
        self.assertEqual(trace[-1]["judge_calls"], 0)
        self.assertTrue(trace[-1]["fast_path"])


class ThresholdTest(unittest.TestCase):
    def test_a_low_scoring_retrieval_skips_the_judge(self):
        """Guardrail 5: reasoning over clauses that do not apply is worse than a rewrite."""
        weak = [candidate(score=0.01)]
        with (
            mock.patch("core.agent.search", return_value=weak),
            mock.patch("core.agent.complete_structured") as judged_call,
        ):
            verdict, trace = audit_line(
                BillLine(item="Physiotherapy", amount=6000, qty=4), POLICY, 300000, VALID
            )
        judged_call.assert_not_called()
        self.assertTrue(verdict.needs_human)
        self.assertEqual(trace[-1]["judge_calls"], 0)


if __name__ == "__main__":
    unittest.main()
