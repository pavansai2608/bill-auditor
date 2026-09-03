"""A room-rent cap may only reduce a room-rent line.

`core/second_pass.py` already refuses to let anything but room rent drive a
proportionate deduction. The judge had no equivalent, so a per-day room cap
could be applied *directly*, as though it governed the line: on B01 the judge
returned `II.1` - Star Health's Rs 5,000/day room limit - for "Medicines and
Drugs" and allowed Rs 5,000 of a Rs 38,000 charge.

The rule, stated without reference to any bill:

    A limit whose basis is per_day, cited from a clause that governs the room
    entitlement, may only be applied to a room-rent line. For any other line the
    verdict is rejected and the loop falls through to its ordinary retry-then-
    abstain path.

Both halves come from the documents, not from the model's prose. A clause
governs the room entitlement when `core.room_limit.governs_room_rent` says so -
it carries the sum-insured rows the entitlement is read from, or its wording
states the limit or defers it to the schedule. A line is a room line by
`second_pass.ROOM_RE`, the same test that picks the line driving a deduction.

The cases where it must *not* fire matter as much as the ones where it must: an
over-eager version of this rule would reject a genuine per-day cap on an ICU or
nursing line and turn correct verdicts into abstentions.
"""

import unittest

from core.agent import _room_cap_on_a_non_room_line
from core.models import BillLine, Clause, JudgeOutput, Limit
from core.retrieve import RetrievedClause
from core.room_limit import governs_room_rent

# A clause that really does state the room entitlement: the sum-insured table.
ROOM_TABLE = Clause(
    clause_id="II.1",
    title="In-patient Treatment",
    text=(
        "In-patient Treatment. The Company will cover room, boarding and nursing expenses.\n"
        "[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day\n"
        "[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room"
    ),
    page=9,
    policy="star_health",
    rule_type="room_rent",
)

# States the entitlement in words instead of a table.
ROOM_WORDING = Clause(
    clause_id="B.1.1",
    title="Hospitalization Expenses",
    text="Room rent limit shall be 'At Actuals' unless otherwise specified in the Policy Schedule.",
    page=11,
    policy="hdfc_ergo",
    rule_type="room_rent",
)

# Mentions room rent, but does not state the entitlement. An ICU sub-limit
# clause of exactly this shape is why the rule keys off the entitlement rather
# than off the words "room rent" appearing anywhere in the text.
MENTIONS_ROOM_ONLY = Clause(
    clause_id="II.9",
    title="Intensive Care Unit",
    text=(
        "Intensive Care Unit charges are payable up to Rs 10,000/- per day. "
        "This is in addition to the room rent payable under this policy."
    ),
    page=12,
    policy="star_health",
    rule_type="sub_limit",
)


def candidates(*clauses: Clause) -> list[RetrievedClause]:
    return [RetrievedClause(clause=c, score=0.9, matched_text=c.text) for c in clauses]


def judged(clause_id: str, *limits: Limit) -> JudgeOutput:
    return JudgeOutput(
        clause_id=clause_id,
        confident=True,
        limits=list(limits),
        reasoning="test",
    )


PER_DAY = Limit(amount=5000.0, basis="per_day")
ABSOLUTE = Limit(amount=75000.0, basis="absolute")


class GovernsRoomRentTest(unittest.TestCase):
    """Which clauses count as stating the room entitlement."""

    def test_a_clause_carrying_the_sum_insured_table_governs_it(self):
        self.assertTrue(governs_room_rent(ROOM_TABLE))

    def test_a_clause_stating_at_actuals_governs_it(self):
        self.assertTrue(governs_room_rent(ROOM_WORDING))

    def test_a_passing_mention_of_room_rent_does_not(self):
        """The ICU clause says "room rent" and states a per-day cap of its own."""
        self.assertFalse(governs_room_rent(MENTIONS_ROOM_ONLY))


class TheGuardrailFiresTest(unittest.TestCase):
    """A per-day room cap offered for something that is not a room."""

    def test_the_b01_case_it_was_written_for(self):
        fired = _room_cap_on_a_non_room_line(
            judged("II.1", PER_DAY),
            BillLine(item="medicines and drugs", amount=38000.0, qty=1),
            candidates(ROOM_TABLE),
        )
        self.assertTrue(fired, "a Rs 5,000/day room cap does not govern medicines")

    def test_it_fires_for_a_surgeon_fee_too(self):
        self.assertTrue(
            _room_cap_on_a_non_room_line(
                judged("II.1", PER_DAY),
                BillLine(item="surgeon fee", amount=80000.0, qty=1),
                candidates(ROOM_TABLE),
            )
        )

    def test_it_fires_on_a_wording_clause_not_only_a_table(self):
        self.assertTrue(
            _room_cap_on_a_non_room_line(
                judged("B.1.1", PER_DAY),
                BillLine(item="investigations - mri", amount=14000.0, qty=1),
                candidates(ROOM_WORDING),
            )
        )

    def test_one_per_day_limit_among_several_is_enough(self):
        self.assertTrue(
            _room_cap_on_a_non_room_line(
                judged("II.1", ABSOLUTE, PER_DAY),
                BillLine(item="anaesthetist charges", amount=15000.0, qty=1),
                candidates(ROOM_TABLE),
            )
        )


class TheGuardrailStaysQuietTest(unittest.TestCase):
    """Every case it must not fire on. An over-eager rule loses correct verdicts."""

    def test_not_on_the_room_line_itself(self):
        for item in (
            "room rent (single a/c) 8,000 x 5 days",
            "room charges",
            "bed charges",
            "accommodation",
        ):
            with self.subTest(item=item):
                self.assertFalse(
                    _room_cap_on_a_non_room_line(
                        judged("II.1", PER_DAY),
                        BillLine(item=item, amount=40000.0, qty=5),
                        candidates(ROOM_TABLE),
                    ),
                    "the room cap is exactly what should govern a room line",
                )

    def test_not_when_the_limit_is_not_per_day(self):
        """A Rs 75,000 absolute cap from the same clause is not a room cap."""
        self.assertFalse(
            _room_cap_on_a_non_room_line(
                judged("II.1", ABSOLUTE),
                BillLine(item="medicines and drugs", amount=38000.0, qty=1),
                candidates(ROOM_TABLE),
            )
        )

    def test_not_when_a_per_day_cap_comes_from_a_clause_of_its_own(self):
        """The case that would break real verdicts: ICU is capped per day too.

        `II.9` states Rs 10,000/day for ICU and mentions room rent in passing.
        Rejecting that would turn a correct ICU verdict into an abstention.
        """
        self.assertFalse(
            _room_cap_on_a_non_room_line(
                judged("II.9", Limit(amount=10000.0, basis="per_day")),
                BillLine(item="icu charges 12,000 x 2 days", amount=24000.0, qty=2),
                candidates(MENTIONS_ROOM_ONLY, ROOM_TABLE),
            ),
            "II.9 states the ICU cap itself; it does not govern the room",
        )

    def test_not_when_the_judge_returned_no_limits_at_all(self):
        self.assertFalse(
            _room_cap_on_a_non_room_line(
                judged("II.1"),
                BillLine(item="medicines and drugs", amount=38000.0, qty=1),
                candidates(ROOM_TABLE),
            )
        )

    def test_not_when_the_cited_clause_was_not_among_the_candidates(self):
        """Nothing to inspect means nothing to reject; guardrail 2 owns that case."""
        self.assertFalse(
            _room_cap_on_a_non_room_line(
                judged("XX.99", PER_DAY),
                BillLine(item="medicines and drugs", amount=38000.0, qty=1),
                candidates(ROOM_TABLE),
            )
        )


if __name__ == "__main__":
    unittest.main()
