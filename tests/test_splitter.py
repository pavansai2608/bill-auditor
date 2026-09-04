"""PyUnit tests for the clause splitter.

These run on synthetic text, not the real PDFs, so they stay fast and keep
working if a policy document is replaced. The behaviours pinned here are the
ones that silently destroyed the output during development: joining lines
before splitting, and letting numbered list items masquerade as clauses.
"""

import unittest

from core import splitter
from core.config import settings
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


class PhantomSpaceTest(unittest.TestCase):
    """A space glyph painted on top of the letter before it is not a word break.

    star_health.pdf emits one at the same cursor position as the first letter
    after a list marker, so the index carried "E xpenses related to the
    treatment" where the page plainly reads "Expenses". BM25 cannot match a term
    broken in half, and a citation cannot be located by quoting it.

    The danger in fixing it is welding together words that are genuinely
    separate, so the rule is narrow and every case below is a real shape from
    the documents. Measured across all four PDFs: 50,297 spaces, 79 caught.
    """

    @staticmethod
    def char(text, x0, x1, top=100.0):
        return {"text": text, "x0": x0, "x1": x1, "top": top, "object_type": "char"}

    def test_the_case_it_was_written_for(self):
        """The real geometry from star_health.pdf page 28, to three decimals."""
        self.assertTrue(
            splitter.is_phantom_space(
                self.char(" ", 347.244, 350.066),
                self.char("E", 347.242, 352.664),
                self.char("x", 352.596, 357.659),
            )
        )

    def test_an_ordinary_word_space_is_left_alone(self):
        """ "Expenses related": the space sits between the glyphs, not inside one."""
        self.assertFalse(
            splitter.is_phantom_space(
                self.char(" ", 395.228, 398.051),
                self.char("s", 389.780, 395.297),
                self.char("r", 397.395, 401.338),
            )
        )

    def test_a_doubled_space_is_never_touched(self):
        """star_health writes "i.  Having", and one of the pair is a real gap.

        Without this, both members of the pair look phantom and the words weld:
        "out  AYUSH" would become "outAYUSH".
        """
        first = self.char(" ", 100.0, 102.8)
        second = self.char(" ", 100.1, 102.9)
        self.assertFalse(splitter.is_phantom_space(second, first, self.char("A", 103.0, 109.0)))
        self.assertFalse(splitter.is_phantom_space(first, self.char("t", 95.0, 100.2), second))

    def test_a_space_on_another_line_cannot_be_contained(self):
        """Sorting brings line ends and line starts together; tops keep them apart."""
        self.assertFalse(
            splitter.is_phantom_space(
                self.char(" ", 100.0, 102.0, top=200.0),
                self.char("W", 99.0, 110.0, top=100.0),
                self.char("a", 103.0, 109.0, top=200.0),
            )
        )

    def test_a_wide_glyph_does_not_swallow_the_space_after_it(self):
        """The narrowest real case: a wide W, then a space, then the next word."""
        self.assertFalse(
            splitter.is_phantom_space(
                self.char(" ", 110.1, 112.9),
                self.char("W", 99.0, 110.0),
                self.char("a", 113.0, 119.0),
            )
        )

    @unittest.skipUnless((settings.policies_dir / "star_health.pdf").exists(), "no PDF")
    def test_the_clause_that_started_this_reads_correctly_now(self):
        pages = splitter.extract_pages(settings.policies_dir / "star_health.pdf")
        text = "\n".join(page.text for page in pages)
        self.assertIn("Expenses related to the treatment", text)
        self.assertNotIn("E xpenses", text)

    @unittest.skipUnless((settings.policies_dir / "star_health.pdf").exists(), "no PDF")
    def test_no_phantom_space_survives_in_any_document(self):
        """The invariant, stated where it can actually be proved.

        A text-level property cannot express this: `[A-Za-z] [a-z]{3,}` matches
        "a cost" and "a health" as readily as "E xpenses", because "a" is a real
        English word. The geometry is unambiguous, so the property is checked
        there - after filtering, no space glyph anywhere is contained in the
        glyph before it.
        """
        import pdfplumber

        offenders = []
        for name in ("star_health.pdf", "hdfc_ergo.pdf", "niva_bupa.pdf", "non_payable_items.pdf"):
            path = settings.policies_dir / name
            if not path.exists():
                continue
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    clean = splitter.without_phantom_spaces(page)
                    chars = sorted(clean.chars, key=lambda c: (round(c["top"], 1), c["x0"]))
                    for index in range(1, len(chars) - 1):
                        if splitter.is_phantom_space(
                            chars[index], chars[index - 1], chars[index + 1]
                        ):
                            offenders.append(f"{name} p{page.page_number}")
        self.assertEqual([], offenders[:10], f"{len(offenders)} phantom spaces survived")

    @unittest.skipUnless((settings.policies_dir / "star_health.pdf").exists(), "no PDF")
    def test_the_titles_it_repaired_are_words_again(self):
        """Six clause headings were split, and a heading is what a citation shows."""
        pages = splitter.extract_pages(settings.policies_dir / "star_health.pdf")
        text = "\n".join(page.text for page in pages)
        for whole, broken in (
            ("Automatic Restoration", "A utomatic Restoration"),
            ("Teaching hospital", "T eaching hospital"),
            ("for transportation", "f or transportation"),
        ):
            with self.subTest(word=whole):
                self.assertIn(whole, text)
                self.assertNotIn(broken, text)
