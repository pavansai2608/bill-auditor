"""PyUnit tests for ingestion.

The non-payable parser is tested on a synthetic table so it runs without the
PDF. The checkpoint tests are skipped when `data/clauses.json` is absent, so a
fresh clone can still run the suite - but once ingestion has run they assert
the invariants every later phase depends on.
"""

import re
import unittest

from core.config import settings
from core.ingest import clause_index, load_clauses, load_non_payable
from core.models import Clause
from core.splitter import TABLE_MARKER


def _checkpoint_missing() -> bool:
    return not settings.clauses_path.exists()


def _prose_chars(text: str) -> int:
    """Characters outside rendered table rows.

    Imported from the splitter rather than restated, so the marker the tests
    measure against cannot drift from the marker the splitter writes.
    """
    return sum(
        len(line) + 1 for line in text.split("\n") if not line.lstrip().startswith(TABLE_MARKER)
    )


class ClauseDocumentTest(unittest.TestCase):
    def test_metadata_carries_the_citation(self):
        from core.ingest import clause_to_document

        clause = Clause(
            clause_id="4.2",
            title="Room Rent Limit",
            # As the splitter writes it: the body already opens with the title.
            text="Room Rent Limit\nRoom rent is limited to 1% of the sum insured per day.",
            page=4,
            policy="demo",
            rule_type="room_rent",
        )
        document = clause_to_document(clause)
        self.assertEqual(document.metadata["clause_id"], "4.2")
        self.assertEqual(document.metadata["policy"], "demo")
        self.assertEqual(document.metadata["rule_type"], "room_rent")
        self.assertIn("Room Rent Limit", document.page_content)
        # The title must appear exactly once - it used to be prepended twice.
        self.assertEqual(document.page_content.count("Room Rent Limit"), 1)


@unittest.skipIf(_checkpoint_missing(), "run 'uv run python -m core.ingest' first")
class CheckpointTest(unittest.TestCase):
    """Invariants the agent and guardrails rely on."""

    @classmethod
    def setUpClass(cls):
        cls.clauses = load_clauses()

    def test_clause_count_is_plausible(self):
        self.assertGreater(len(self.clauses), 150)
        self.assertLess(len(self.clauses), 600)

    def test_every_policy_is_represented(self):
        policies = {c.policy for c in self.clauses}
        self.assertEqual(policies, {"star_health", "hdfc_ergo", "niva_bupa"})

    def test_clause_ids_are_unique_within_a_policy(self):
        seen = set()
        for clause in self.clauses:
            key = (clause.policy, clause.clause_id)
            self.assertNotIn(key, seen, f"duplicate {key}")
            seen.add(key)

    def test_clause_ids_look_like_citations(self):
        # 4.2 | 5.3.1 | A.1.1 | II.28 | A.1.1.Def41 | I.Def41
        pattern = re.compile(r"^(?:[A-Z]{1,4}\.)?(?:\d+(?:\.\d+)*(?:\.Def\d+)?|Def\d+)$")
        for clause in self.clauses:
            self.assertRegex(clause.clause_id, pattern)

    def test_no_clause_is_empty(self):
        for clause in self.clauses:
            self.assertGreater(len(clause.text), 40, clause.clause_id)

    def test_no_clause_carries_an_enormous_body_of_prose(self):
        """Under-split PROSE is what swamps num_ctx, so prose is what is capped.

        The ceiling used to count every character, table rows included, and
        `hdfc_ergo E.2` broke it at 12,414 - of which 9,749 (78.5%) are rendered
        `[table]` rows and 2,666 are prose. E.2 is not under-split; it is a
        plan-comparison grid and the legend that reads it, and the legend is
        worth nothing detached from the grid.

        Exempting "predominantly table" clauses outright was the obvious repair
        and is the weaker one: a fraction is a ratio, and a ratio puts no bound
        on the absolute prose payload. A clause of 40,000 characters of table
        and 13,000 of prose is 75% table and would be waved through carrying
        more prose than the ceiling was ever willing to allow. Measuring the
        prose directly has no such hole and no threshold to tune - and on this
        index it exempts exactly the clause it should: E.2 is the only one of
        399 above the old ceiling, and no clause is even close to 12,000
        characters of prose.
        """
        for clause in self.clauses:
            self.assertLess(_prose_chars(clause.text), 12_000, clause.clause_id)

    def test_no_clause_can_eat_the_context_window_on_its_own(self):
        """The other half of the old ceiling: a table is still tokens.

        Capping prose alone would leave a runaway table unbounded, and
        `num_ctx` is 8192 tokens for the whole judge prompt - the bill line, the
        instructions and every retrieved clause together. At roughly four
        characters to the token, 16,000 characters is about half that window in
        one clause, which is the most any single citation may take while
        several are retrieved. E.2, the largest in the index at 12,414, sits
        under it with room to spare.
        """
        for clause in self.clauses:
            self.assertLess(len(clause.text), 16_000, clause.clause_id)

    def test_pages_are_within_the_document(self):
        for clause in self.clauses:
            self.assertGreaterEqual(clause.page, 1)

    def test_index_is_keyed_for_guardrail_lookups(self):
        index = clause_index()
        sample = self.clauses[0]
        self.assertIn(f"{sample.policy}:{sample.clause_id}", index)

    def test_room_rent_is_findable_in_every_policy(self):
        """The whole system turns on room rent; each policy must have one."""
        for policy in ("star_health", "hdfc_ergo", "niva_bupa"):
            hits = [c for c in self.clauses if c.policy == policy and "room rent" in c.text.lower()]
            self.assertTrue(hits, f"no room rent clause found for {policy}")

    def test_star_health_definitions_are_indexed(self):
        """Star Health writes definitions unnumbered; they were dropped entirely.

        Without them "Room Rent means ... and shall include the associated
        medical expenses" is not in the index, and that sentence is what makes
        the proportionate deduction reach the surgeon's fee.
        """
        definitions = [
            c for c in self.clauses if c.policy == "star_health" and c.clause_id.startswith("I.Def")
        ]
        self.assertGreater(len(definitions), 40, "definitions section is missing")
        room_rent = [c for c in definitions if c.title.lower() == "room rent"]
        self.assertTrue(room_rent, "no Room Rent definition indexed for star_health")
        self.assertIn("associated medical expenses", room_rent[0].text.lower())

    def test_titles_are_clean(self):
        """Column breaks used to leave titles cut mid-phrase or letter-spaced."""
        for clause in self.clauses:
            self.assertFalse(
                re.match(r"^[B-HJ-Z]\s[a-z]", clause.title),
                f"letter-spaced title: {clause.title!r}",
            )
            self.assertNotIn(":", clause.title, f"title carries a sentence: {clause.title!r}")

    def test_shortened_titles_never_drop_text_from_the_body(self):
        """The title is a label; the body must keep the whole heading line."""
        star = [c for c in self.clauses if c.policy == "star_health" and c.clause_id == "II.1"]
        self.assertTrue(star)
        self.assertIn("We will cover the", star[0].text)

    def test_rule_types_were_actually_assigned(self):
        """If labelling silently failed, everything would be 'other'."""
        non_other = [c for c in self.clauses if c.rule_type != "other"]
        self.assertGreater(len(non_other), 20)


@unittest.skipIf(not settings.non_payable_path.exists(), "run ingestion first")
class NonPayableTest(unittest.TestCase):
    def test_list_is_populated_and_clean(self):
        entries = load_non_payable()
        self.assertGreater(len(entries), 30)
        names = [e["item"] for e in entries]
        self.assertEqual(len(names), len({n.lower() for n in names}), "duplicates present")
        for name in names:
            self.assertNotIn("\n", name)
            self.assertEqual(name, name.strip())

    def test_every_entry_is_numbered(self):
        """A verdict cites IRDAI-List-I #44, so the serial has to survive."""
        numbers = [e["no"] for e in load_non_payable()]
        self.assertTrue(all(isinstance(n, int) and n > 0 for n in numbers))
        self.assertEqual(len(numbers), len(set(numbers)), "duplicate serial numbers")

    def test_contains_known_consumables(self):
        lowered = {e["item"].lower() for e in load_non_payable()}
        for expected in ("baby food", "beauty services", "laundry charges", "gloves"):
            self.assertIn(expected, lowered)

    def test_syringes_are_not_on_the_list(self):
        """Gloves are excluded, syringes are not - the key has to decide it."""
        lowered = " | ".join(e["item"].lower() for e in load_non_payable())
        self.assertIn("gloves", lowered)
        self.assertNotIn("syringe", lowered)


if __name__ == "__main__":
    unittest.main()
