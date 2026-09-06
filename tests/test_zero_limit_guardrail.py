"""A limit of zero must be supported by the clause it cites.

Guardrail 2 asks whether a cited clause **exists**. Nothing asked whether it
**says** what the verdict claims. So on B41 and B42 the judge returned
`limits=[{amount: 0.0}]` citing `star_health II.1` for anaesthetist charges,
II.1 being the in-patient coverage clause - "We will cover the following Medical
Expenses" - which states no zero limit and mentions no anaesthetist. The
citation was real, so every check passed, and the report told the insured that
Rs 26,000 was not payable with a clause reference beside it.

Measured over the whole 44-bill eval before this rule existed: **8 zero limits,
every one of them wrong.** Seven became a confident `Rs 0` on a line the answer
key pays in full - B05 anaesthetist (key 12,000), B07 ICU (10,000), B14
anaesthetist (16,000), B21 ambulance (1,800), B28 ambulance (4,000), and B41/B42
where the key says flag. Zero is not one wrong number among many; it is the
claim that the policy excludes the expense.

The rule, without reference to any bill:

    A verdict stating a limit of zero is rejected unless the clause it cites
    contains exclusionary language. The verdict then falls through to the
    ordinary retry-then-abstain path.

Only zero is checked. Verifying every rupee figure against its clause is a much
larger problem with real false-rejection risk - percentages, "10% of Sum Insured
or Rs 1,00,000 whichever is less", figures read from a table - and this rule
deliberately does not attempt it.

The cases where it must *not* fire matter as much as the ones where it must. A
policy that genuinely excludes something, or states "Not Available" in a benefit
table, must still be able to produce a zero.
"""

import json
import unittest
from pathlib import Path

from core.agent import _unsupported_zero_limit
from core.config import settings
from core.exclusion import EXCLUSION_RE, is_zero, states_an_exclusion
from core.models import Clause, JudgeOutput, Limit
from core.retrieve import RetrievedClause

ROOT = Path(__file__).resolve().parents[1]

# The clause B41 and B42 cited. In-patient coverage: it grants, it does not
# exclude, and it says nothing about an anaesthetist.
COVERAGE = Clause(
    clause_id="II.1",
    title="In-patient Treatment",
    text=(
        "In-patient Treatment: We will cover the following Medical Expenses incurred in "
        "respect of Hospitalization of the Insured Person during the Policy Period, up to "
        "the Sum Insured specified in the Policy Schedule against this In-Patient treatment:\n"
        "i. Room, Boarding, Nursing Expenses all-inclusive as provided by the Hospital\n"
        "[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day"
    ),
    page=9,
    policy="star_health",
    rule_type="room_rent",
)

# A real exclusion, in the standard IRDAI wording.
EXCLUDES = Clause(
    clause_id="III.2",
    title="Specified disease / procedure waiting period - Code Excl 02",
    text=(
        "Expenses related to the treatment of the following listed Conditions, surgeries/"
        "treatments shall be excluded until the expiry of 24 months of continuous coverage."
    ),
    page=28,
    policy="star_health",
    rule_type="waiting_period",
)

# The benefit-table form. star_health grants shared accommodation "Not Available"
# at the two lowest sums insured, and a zero read off that row is correct.
TABLE_EXCLUSION = Clause(
    clause_id="II.20",
    title="Shared accommodation",
    text=(
        "Shared accommodation: If the Insured Person occupies a shared accommodation, then "
        "amount as per table given below will be payable\n"
        "[table] Sum Insured (Rs.) 1,00,000/- - Limit per day (Rs.) Not Available\n"
        "[table] Sum Insured (Rs.) 3,00,000/- - Limit per day (Rs.) 800/- per day"
    ),
    page=15,
    policy="star_health",
    rule_type="sub_limit",
)

# Carries the exclusion only in its heading. A heading is part of what a clause
# says, so this must pass.
TITLE_ONLY = Clause(
    clause_id="E.2.1",
    title="Not Covered",
    text="800 per day 800 per day 1000 per day 800 per day",
    page=40,
    policy="hdfc_ergo",
    rule_type="other",
)


def candidates(*clauses: Clause) -> list[RetrievedClause]:
    return [RetrievedClause(clause=c, score=0.9, matched_text=c.text) for c in clauses]


def judged(clause_id: str, *limits: Limit) -> JudgeOutput:
    return JudgeOutput(clause_id=clause_id, confident=True, limits=list(limits), reasoning="test")


ZERO = Limit(amount=0.0, basis="absolute")
ZERO_PERCENT = Limit(percentage=0.0, of="sum_insured", basis="absolute")
REAL = Limit(amount=5000.0, basis="per_day")


class WhatCountsAsAnExclusionTest(unittest.TestCase):
    def test_a_coverage_clause_excludes_nothing(self):
        self.assertFalse(states_an_exclusion(COVERAGE))

    def test_the_standard_exclusion_wording_counts(self):
        self.assertTrue(states_an_exclusion(EXCLUDES))

    def test_a_benefit_table_saying_not_available_counts(self):
        """The policy said it; a table row is still the policy saying it."""
        self.assertTrue(states_an_exclusion(TABLE_EXCLUSION))

    def test_an_exclusion_in_the_heading_alone_counts(self):
        self.assertTrue(states_an_exclusion(TITLE_ONLY))

    def test_every_form_these_documents_actually_use(self):
        for phrase in (
            "this expense is not payable under the policy",
            "such charges are not covered",
            "the Company shall not be liable for any amount",
            "does not include cost of pharmacy and consumables",
            "shall be excluded until the expiry of 24 months",
            "Code Excl02",
            "Excl03",
            "Standard Exclusions applicable to this policy",
            "the limit is Nil for this benefit",
            "no claim shall be payable in respect of",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(EXCLUSION_RE.search(phrase), phrase)

    def test_ordinary_granting_language_is_not_an_exclusion(self):
        for phrase in (
            "We will cover the following Medical Expenses",
            "expenses up to Rs 5,000 per day shall be payable",
            "Associated Medical Expenses means nursing charges and operation theatre charges",
            "road ambulance expenses up to Rs.750/- per hospitalization",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(EXCLUSION_RE.search(phrase), phrase)


class TheGuardrailFiresTest(unittest.TestCase):
    def test_the_b41_case_it_was_written_for(self):
        rejected = _unsupported_zero_limit(judged("II.1", ZERO), candidates(COVERAGE))
        self.assertIsNotNone(rejected, "II.1 grants cover; it cannot support a zero")
        self.assertEqual("II.1", rejected.clause_id)

    def test_a_zero_percentage_is_the_same_claim(self):
        self.assertIsNotNone(
            _unsupported_zero_limit(judged("II.1", ZERO_PERCENT), candidates(COVERAGE))
        )

    def test_one_zero_among_several_limits_is_enough(self):
        self.assertIsNotNone(
            _unsupported_zero_limit(judged("II.1", REAL, ZERO), candidates(COVERAGE))
        )


class TheGuardrailStaysQuietTest(unittest.TestCase):
    """Every case it must not fire on. Blocking an honest zero loses a correct line."""

    def test_not_when_the_clause_really_does_exclude(self):
        self.assertIsNone(_unsupported_zero_limit(judged("III.2", ZERO), candidates(EXCLUDES)))

    def test_not_when_a_benefit_table_says_not_available(self):
        self.assertIsNone(
            _unsupported_zero_limit(judged("II.20", ZERO), candidates(TABLE_EXCLUSION))
        )

    def test_not_when_the_exclusion_is_only_in_the_heading(self):
        self.assertIsNone(_unsupported_zero_limit(judged("E.2.1", ZERO), candidates(TITLE_ONLY)))

    def test_not_when_the_limit_is_not_zero(self):
        """The whole point of starting narrow: a real figure is not checked."""
        self.assertIsNone(_unsupported_zero_limit(judged("II.1", REAL), candidates(COVERAGE)))

    def test_not_when_there_are_no_limits_at_all(self):
        self.assertIsNone(_unsupported_zero_limit(judged("II.1"), candidates(COVERAGE)))

    def test_not_when_the_cited_clause_was_not_among_the_candidates(self):
        """Nothing to inspect means nothing to reject; guardrail 2 owns that case."""
        self.assertIsNone(_unsupported_zero_limit(judged("XX.99", ZERO), candidates(COVERAGE)))

    def test_the_irdai_fast_path_is_untouched(self):
        """61 lines a run are zeroed by the non-payable list, with no judge call.

        Those never reach `grade`, so this rule cannot reach them either - but a
        future refactor that routed them through the judge would break 61 correct
        lines at once, so the boundary is asserted rather than assumed.
        """
        self.assertIsNone(_unsupported_zero_limit(judged("IRDAI-List-I", ZERO), candidates()))


class TheBillsItWasWrittenForTest(unittest.TestCase):
    """B41 and B42 as regressions, from the real fixtures rather than a stub.

    Both are star_health at a 10,00,000 sum insured, where the entitlement is a
    room *category* with no rupee figure. The room billed is Deluxe, above that
    category, so a proportionate deduction may apply but no ratio can be built -
    and the key therefore flags every associated line. The system answered
    `Rs 0` for the anaesthetist on both.
    """

    def setUp(self):
        self.key = json.loads((ROOT / "eval" / "answer_key.json").read_text(encoding="utf-8"))

    def test_the_key_flags_both_anaesthetist_lines(self):
        for bill in ("B41", "B42"):
            with self.subTest(bill=bill):
                line = next(
                    ln for ln in self.key["bills"][bill]["lines"] if "Anaesthetist" in ln["item"]
                )
                self.assertTrue(line["needs_human"], "the key must still flag this line")
                self.assertIsNone(line["allowed"])

    @unittest.skipUnless(settings.clauses_path.exists(), "data/clauses.json not built")
    def test_the_clause_they_cited_cannot_support_a_zero(self):
        """The real II.1 out of the index, not the stub above."""
        from core.ingest import load_clauses

        real = next(
            c for c in load_clauses() if c.policy == "star_health" and c.clause_id == "II.1"
        )
        self.assertFalse(states_an_exclusion(real), "II.1 grants cover, it excludes nothing")
        self.assertIsNotNone(
            _unsupported_zero_limit(judged("II.1", ZERO), candidates(real)),
            "a Rs 0 limit citing II.1 must be rejected",
        )

    @unittest.skipUnless(settings.clauses_path.exists(), "data/clauses.json not built")
    def test_every_clause_a_zero_was_read_from_is_classified_the_way_it_should_be(self):
        """The eight zero limits the eval produced, and what this rule says of each."""
        from core.ingest import load_clauses

        clauses = {(c.policy, c.clause_id): c for c in load_clauses()}
        expected = {
            ("star_health", "II.1"): False,  # coverage - rejected
            ("star_health", "II.20"): True,  # "Not Available" in the benefit table
            ("niva_bupa", "5.1.2"): True,  # Code Excl02 waiting period
        }
        for cid, wanted in expected.items():
            with self.subTest(clause=cid):
                self.assertEqual(wanted, states_an_exclusion(clauses[cid]))

    @unittest.skipUnless(settings.clauses_path.exists(), "data/clauses.json not built")
    def test_the_fourth_clause_no_longer_reaches_this_guardrail_at_all(self):
        """`hdfc_ergo E.2.1` was the fourth, and an earlier guardrail now stops it.

        It was the one this rule could not judge: a row of a plan-comparison
        grid read straight across, headed "Not Covered", lexically identical to
        `star_health II.20` - which says the same words and is a *correct* zero.
        `KNOWN_LIMITATIONS.md` section 10 records that no test over the text's
        meaning separates the two.

        The splitter fix removed it from the index, so the two zeros read off it
        on B21 and B28 are now rejected by guardrail 2 as a citation that does
        not resolve, before this rule is ever asked. **That closes those two
        lines. It does not close the hole** - the next flattened table would
        land in it the same way - which is why section 10 stays.
        """
        from core.ingest import load_clauses

        hdfc = [c for c in load_clauses() if c.policy == "hdfc_ergo"]

        # 1. It is gone from the index, at source. If this fails the splitter has
        #    regressed and this rule is once again the only thing standing
        #    between a flattened table row and a wrong Rs 0.
        self.assertNotIn(
            "E.2.1",
            {c.clause_id for c in hdfc},
            "E.2.1 is back in the index; the splitter has regressed",
        )

        # 2. Guardrail 2 is what now rejects a zero citing it. `valid_ids` is
        #    built from the policy's own clauses, so an id that is not in the
        #    index cannot be in that set, and `grade` abstains on the citation
        #    before it ever asks whether the clause states an exclusion.
        valid_ids = {c.clause_id for c in hdfc}
        self.assertNotIn("E.2.1", valid_ids)

        # 3. And there is nothing left to read a zero off. Handed the whole of
        #    hdfc_ergo as candidates, a verdict citing E.2.1 resolves to no
        #    clause at all - so this rule returns None for want of anything to
        #    inspect, not because it judged the text exclusionary. That is the
        #    distinction the old assertion could not make: it passed because
        #    `states_an_exclusion` said True of a corrupt clause, which was the
        #    right answer to the wrong question.
        self.assertIsNone(
            _unsupported_zero_limit(judged("E.2.1", ZERO), candidates(*hdfc)),
            "nothing in hdfc_ergo answers to E.2.1, so nothing can support a zero",
        )
        self.assertIsNone(
            next((c for c in hdfc if c.clause_id == "E.2.1"), None),
            "a clause answering to E.2.1 is exactly what must not come back",
        )


class IsZeroTest(unittest.TestCase):
    def test_it_recognises_both_shapes(self):
        self.assertTrue(is_zero(ZERO))
        self.assertTrue(is_zero(ZERO_PERCENT))
        self.assertFalse(is_zero(REAL))
        self.assertFalse(is_zero(Limit(percentage=10.0, of="sum_insured", basis="absolute")))


if __name__ == "__main__":
    unittest.main()
