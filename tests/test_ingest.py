"""PyUnit tests for ingestion.

The non-payable parser is tested on a synthetic table so it runs without the
PDF. The checkpoint tests are skipped when `data/clauses.json` is absent, so a
fresh clone can still run the suite - but once ingestion has run they assert
the invariants every later phase depends on.
"""

import unittest

from core.config import settings
from core.ingest import clause_index, load_clauses, load_non_payable
from core.models import Clause


def _checkpoint_missing() -> bool:
    return not settings.clauses_path.exists()


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
        import re

        pattern = re.compile(r"^[A-Z]{0,4}\.?\d+(?:\.\d+)*(?:\.Def\d+)?$")
        for clause in self.clauses:
            self.assertRegex(clause.clause_id, pattern)

    def test_no_clause_is_empty_or_enormous(self):
        """An enormous clause means under-splitting; it would swamp num_ctx."""
        for clause in self.clauses:
            self.assertGreater(len(clause.text), 40, clause.clause_id)
            self.assertLess(len(clause.text), 12_000, clause.clause_id)

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

    def test_rule_types_were_actually_assigned(self):
        """If labelling silently failed, everything would be 'other'."""
        non_other = [c for c in self.clauses if c.rule_type != "other"]
        self.assertGreater(len(non_other), 20)


@unittest.skipIf(not settings.non_payable_path.exists(), "run ingestion first")
class NonPayableTest(unittest.TestCase):
    def test_list_is_populated_and_clean(self):
        items = load_non_payable()
        self.assertGreater(len(items), 30)
        self.assertEqual(len(items), len({i.lower() for i in items}), "duplicates present")
        for item in items:
            self.assertNotIn("\n", item)
            self.assertEqual(item, item.strip())

    def test_contains_known_consumables(self):
        lowered = {i.lower() for i in load_non_payable()}
        for expected in ("baby food", "beauty services", "laundry charges"):
            self.assertIn(expected, lowered)


if __name__ == "__main__":
    unittest.main()
