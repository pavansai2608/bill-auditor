"""PyUnit tests for the clause splitter.

These run on synthetic text, not the real PDFs, so they stay fast and keep
working if a policy document is replaced. The behaviours pinned here are the
ones that silently destroyed the output during development: joining lines
before splitting, and letting numbered list items masquerade as clauses.
"""

import unittest

from core.models import Clause
from core.splitter import (
    CLAUSE_RE,
    PageText,
    _is_address_noise,
    _looks_like_title,
    _section_at,
    _split_definitions,
    clean_pages,
    find_furniture,
    join_wrapped_lines,
    split_clauses,
)


class ClausePatternTest(unittest.TestCase):
    def test_matches_dotted_and_bare_numbers(self):
        for line, number in [
            ("4.2 Room Rent Limit", "4.2"),
            ("4.2. Room Rent Limit", "4.2"),
            ("5.3.1 Proportionate Deduction", "5.3.1"),
            ("27. Treatment in Valuable Service Providers", "27"),
        ]:
            with self.subTest(line=line):
                match = CLAUSE_RE.match(line)
                self.assertIsNotNone(match, line)
                self.assertEqual(match.group(1), number)

    def test_title_must_open_like_a_heading(self):
        self.assertTrue(_looks_like_title("Room Rent Limit"))
        self.assertTrue(_looks_like_title("30-day waiting period"))
        # A numbered list item continues a sentence and starts lower-case.
        self.assertFalse(_looks_like_title("it needs ongoing monitoring"))
        # Pure figures are table rows, not headings.
        self.assertFalse(_looks_like_title("5,000 / 10,000"))
        self.assertFalse(_looks_like_title(""))


class SectionTest(unittest.TestCase):
    def test_detects_lettered_and_roman_banners(self):
        self.assertEqual(_section_at("SECTION B. BENEFITS"), "B")
        self.assertEqual(_section_at("II. Coverage"), "II")
        self.assertIsNone(_section_at("2.1 Definitions of terms used here"))

    def test_section_qualifies_colliding_ids(self):
        """1.1 appears under both Definitions and Benefits and must not collide."""
        pages = [
            PageText(
                page=1,
                text=(
                    "SECTION A. DEFINITIONS\n"
                    "1.1 Standard Definitions\n"
                    + "Terms used in this policy carry the meanings set out below. "
                    * 3
                    + "\nSECTION B. BENEFITS\n"
                    "1.1 Hospitalization Expenses\n"
                    + "The Company shall indemnify medical expenses necessarily incurred. "
                    * 3
                ),
            )
        ]
        clauses = split_clauses(pages, "test")
        ids = [c.clause_id for c in clauses]
        self.assertEqual(ids, ["A.1.1", "B.1.1"])


class JoinWrappedLinesTest(unittest.TestCase):
    def test_joins_mid_sentence_breaks(self):
        text = "The Company shall indemnify medical\nexpenses incurred by the Insured Person."
        self.assertEqual(
            join_wrapped_lines(text),
            "The Company shall indemnify medical expenses incurred by the Insured Person.",
        )

    def test_stitches_hyphenated_breaks(self):
        self.assertEqual(join_wrapped_lines("Pre-hospitali-\nsation"), "Pre-hospitalisation")

    def test_never_joins_across_a_clause_start(self):
        text = "charges shall be payable\n4.2 Room Rent Limit\nThe limit is 1% of Sum Insured."
        self.assertIn("\n4.2 Room Rent Limit\n", join_wrapped_lines(text))


class SplitClausesTest(unittest.TestCase):
    def _pages(self):
        return [
            PageText(
                page=4,
                text=(
                    "4.1 Hospitalization\n"
                    "We cover hospitalization expenses incurred during the policy year "
                    "up to the sum insured stated in the schedule.\n"
                    "4.2 Room Rent Limit\n"
                    "Room rent is limited to 1% of the sum insured per day. Where the\n"
                    "insured occupies a higher category room the limit still applies.\n"
                ),
            ),
            PageText(
                page=5,
                text=(
                    "and no further amount is payable under this benefit.\n"
                    "4.3 Co-payment\n"
                    "A co-payment of 20% applies to every claim made by an insured "
                    "person aged 61 years or above at the time of first enrolment.\n"
                ),
            ),
        ]

    def test_splits_on_clause_numbers(self):
        clauses = split_clauses(self._pages(), "demo")
        self.assertEqual([c.clause_id for c in clauses], ["4.1", "4.2", "4.3"])
        self.assertEqual(clauses[1].title, "Room Rent Limit")
        self.assertEqual(clauses[1].page, 4)
        self.assertEqual(clauses[0].policy, "demo")

    def test_clause_survives_a_page_break(self):
        """4.2 starts on page 4 and finishes on page 5 - it must stay one clause."""
        clauses = split_clauses(self._pages(), "demo")
        room_rent = next(c for c in clauses if c.clause_id == "4.2")
        self.assertIn("no further amount is payable", room_rent.text)
        self.assertNotIn("Co-payment", room_rent.text)

    def test_never_splits_inside_a_clause(self):
        pages = [
            PageText(
                page=1,
                text=(
                    "3.1 Excluded Expenses\n"
                    "The following are not payable under any circumstances:\n"
                    "a. gloves, masks and other consumables used during the procedure\n"
                    "b. registration and admission charges levied by the hospital\n"
                    "i. items billed separately from the main treatment invoice\n"
                ),
            )
        ]
        clauses = split_clauses(pages, "demo")
        self.assertEqual(len(clauses), 1)
        self.assertIn("gloves", clauses[0].text)
        self.assertIn("registration", clauses[0].text)

    def test_drops_headings_with_no_body(self):
        """Table-of-contents entries look like clauses but carry nothing."""
        pages = [PageText(page=1, text="4.1 Hospitalization\n4.2 Room Rent\n4.3 Co-payment\n")]
        self.assertEqual(split_clauses(pages, "demo"), [])


class CleaningTest(unittest.TestCase):
    def test_finds_and_strips_repeated_furniture(self):
        header = "ACME INSURANCE COMPANY LIMITED | POLICY WORDINGS"
        pages = [PageText(page=i, text=f"{header}\nbody text for page {i}") for i in range(1, 6)]
        self.assertIn(header, find_furniture(pages))
        cleaned = clean_pages(pages)
        self.assertNotIn(header, cleaned[0].text)
        self.assertIn("body text for page 1", cleaned[0].text)

    def test_keeps_lines_that_appear_only_once(self):
        pages = [PageText(page=i, text=f"unique line {i}") for i in range(1, 6)]
        self.assertEqual(find_furniture(pages), set())


class DefinitionSplitTest(unittest.TestCase):
    def test_splits_a_definitions_block_per_term(self):
        block = Clause(
            clause_id="A.1.1",
            title="Standard Definitions",
            text="\n".join(
                [
                    "The terms below have the meanings given.",
                    "Def. 1. Accident means a sudden, unforeseen and involuntary event.",
                    "Def. 2. Any one illness means a continuous period of illness including relapse.",
                    "Def. 3. Cashless Facility means a facility where the insurer pays the hospital.",
                    "Def. 4. Hospital means an institution established for in-patient care.",
                    "Def. 5. Room Rent means the amount charged by a Hospital towards boarding.",
                    "Def. 6. Surgery means a manual or operative procedure performed by a surgeon.",
                ]
            ),
            page=2,
            policy="demo",
        )
        parts = _split_definitions(block)
        self.assertEqual(len(parts), 6)
        self.assertEqual(parts[4].clause_id, "A.1.1.Def5")
        self.assertEqual(parts[4].title, "Room Rent")
        self.assertTrue(parts[4].text.startswith("Room Rent means"))

    def test_leaves_a_short_block_alone(self):
        clause = Clause(
            clause_id="A.1",
            title="Definitions",
            text="Def. 1. Accident means an event.",
            page=1,
            policy="demo",
        )
        self.assertEqual(_split_definitions(clause), [clause])


class AddressNoiseTest(unittest.TestCase):
    def test_flags_an_ombudsman_annexure(self):
        clause = Clause(
            clause_id="E.1",
            title="Annexure",
            text=(
                "Office of the Insurance Ombudsman, Ahmedabad. Tel.: 079-25501201 "
                "Email: bimalokpal.ahmedabad@cioins.co.in BENGALURU Office of the "
                "Insurance Ombudsman Tel.: 080-26652048 Email: x@cioins.co.in"
            ),
            page=45,
            policy="demo",
        )
        self.assertTrue(_is_address_noise(clause))

    def test_keeps_a_real_clause(self):
        clause = Clause(
            clause_id="4.2",
            title="Room Rent Limit",
            text="Room rent is limited to 1% of the sum insured per day.",
            page=4,
            policy="demo",
        )
        self.assertFalse(_is_address_noise(clause))


if __name__ == "__main__":
    unittest.main()
