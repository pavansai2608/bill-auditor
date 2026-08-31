"""PyUnit tests for hybrid retrieval.

Split in two. The sub-chunking and rerank-collapse logic is pure and tested
directly on synthetic documents, so it runs in milliseconds with no models
loaded. The end-to-end searches need Chroma and two transformer models, so they
are skipped unless the index exists and are marked slow.
"""

import unittest
from itertools import pairwise

from langchain_core.documents import Document

from core.config import settings
from core.retrieve import (
    SUB_CHUNK_THRESHOLD,
    ClauseReranker,
    ClauseSubChunker,
    sentence_windows,
)


class SentenceWindowTest(unittest.TestCase):
    def test_packs_sentences_up_to_the_target(self):
        text = " ".join(f"Sentence number {i} says something about the policy." for i in range(20))
        windows = sentence_windows(text, target=200)
        self.assertGreater(len(windows), 1)
        for window in windows:
            self.assertLess(len(window), 400)

    def test_windows_overlap_by_one_sentence(self):
        """A rule split across a boundary must survive intact in one window."""
        text = (
            "The room rent limit is 1% of Sum Insured. "
            "Where this limit is exceeded all other charges are reduced. "
            "This does not apply to ICU. "
            "Ambulance charges are covered separately."
        )
        windows = sentence_windows(text, target=60)
        joined = " ".join(windows)
        self.assertIn("Where this limit is exceeded", joined)
        # Consecutive windows share their boundary sentence.
        self.assertTrue(
            any(w1.split(". ")[-1] and w1.split(". ")[-1] in w2 for w1, w2 in pairwise(windows))
        )

    def test_empty_text_yields_nothing(self):
        self.assertEqual(sentence_windows(""), [])
        self.assertEqual(sentence_windows("   "), [])


class SubChunkerTest(unittest.TestCase):
    def _long_document(self):
        body = (
            "We will cover the following medical expenses incurred during hospitalization. " * 12
            + "Room rent is limited to Rs 5,000 per day for this sum insured. "
            + "Ambulance charges are payable up to Rs 2,000 per hospitalization. " * 12
        )
        return Document(
            page_content=body,
            metadata={
                "clause_id": "II.1",
                "policy": "star_health",
                "title": "In-patient Treatment",
                "page": 9,
            },
        )

    def test_short_documents_pass_through_untouched(self):
        short = Document(page_content="Room rent is capped at 1%.", metadata={"clause_id": "4.2"})
        out = ClauseSubChunker().transform_documents([short])
        self.assertEqual(len(out), 1)
        self.assertIs(out[0], short)

    def test_long_documents_are_split(self):
        document = self._long_document()
        self.assertGreater(len(document.page_content), SUB_CHUNK_THRESHOLD)
        out = ClauseSubChunker().transform_documents([document])
        self.assertGreater(len(out), 1)

    def test_every_sub_chunk_keeps_the_parent_citation(self):
        """This is what makes the citation still resolve after sub-chunking."""
        out = ClauseSubChunker().transform_documents([self._long_document()])
        for chunk in out:
            self.assertEqual(chunk.metadata["clause_id"], "II.1")
            self.assertEqual(chunk.metadata["policy"], "star_health")
            self.assertEqual(chunk.metadata["sub_chunk_of"], "II.1")
            self.assertIn("sub_chunk", chunk.metadata)

    def test_the_buried_sentence_gets_its_own_chunk(self):
        out = ClauseSubChunker().transform_documents([self._long_document()])
        carrying = [c for c in out if "5,000 per day" in c.page_content]
        self.assertEqual(
            len(carrying), 1, "the room rent sentence should sit in exactly one window"
        )
        # It is no longer drowned by the rest of the clause.
        self.assertLess(len(carrying[0].page_content), len(self._long_document().page_content) / 2)

    def test_sub_chunks_carry_the_title_for_context(self):
        out = ClauseSubChunker().transform_documents([self._long_document()])
        for chunk in out:
            self.assertTrue(chunk.page_content.startswith("In-patient Treatment"))


class RerankCollapseTest(unittest.TestCase):
    """The reranker must return distinct clauses, not several windows of one."""

    class _StubEncoder:
        def __init__(self, scores):
            self.scores = scores

        def score(self, pairs):
            return self.scores[: len(pairs)]

    def _run(self, documents, scores, top_n=3):
        import core.retrieve as retrieve

        original = retrieve.get_cross_encoder
        retrieve.get_cross_encoder = lambda: self._StubEncoder(scores)
        try:
            return ClauseReranker(top_n=top_n).compress_documents(documents, "room rent")
        finally:
            retrieve.get_cross_encoder = original

    def test_keeps_the_best_window_per_clause(self):
        documents = [
            Document(page_content="a", metadata={"clause_id": "II.1", "policy": "star_health"}),
            Document(page_content="b", metadata={"clause_id": "II.1", "policy": "star_health"}),
            Document(page_content="c", metadata={"clause_id": "II.9", "policy": "star_health"}),
        ]
        out = self._run(documents, [0.2, 0.9, 0.5])
        self.assertEqual([d.metadata["clause_id"] for d in out], ["II.1", "II.9"])
        self.assertAlmostEqual(out[0].metadata["relevance_score"], 0.9)
        self.assertEqual(out[0].page_content, "b", "the higher-scoring window should win")

    def test_same_id_in_different_policies_is_not_collapsed(self):
        documents = [
            Document(page_content="a", metadata={"clause_id": "1.1", "policy": "hdfc_ergo"}),
            Document(page_content="b", metadata={"clause_id": "1.1", "policy": "niva_bupa"}),
        ]
        out = self._run(documents, [0.4, 0.8])
        self.assertEqual(len(out), 2)

    def test_respects_top_n(self):
        documents = [
            Document(page_content=str(i), metadata={"clause_id": f"c{i}", "policy": "p"})
            for i in range(6)
        ]
        out = self._run(documents, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6], top_n=3)
        self.assertEqual(len(out), 3)
        self.assertEqual([d.metadata["clause_id"] for d in out], ["c5", "c4", "c3"])

    def test_empty_input_is_safe(self):
        self.assertEqual(ClauseReranker().compress_documents([], "room rent"), [])


@unittest.skipUnless(
    settings.db_dir.exists() and any(settings.db_dir.iterdir()),
    "vector store missing - run 'uv run python -m core.ingest'",
)
class EndToEndSearchTest(unittest.TestCase):
    """Slow: loads Chroma, bge-base and the cross-encoder."""

    def test_finds_the_room_rent_rule_in_each_policy(self):
        from core.retrieve import search

        expected = {
            # Star Health states its per-day table inside a long benefits clause.
            "star_health": ("room rent limit per day", "II.1"),
            # HDFC's proportionate deduction lives inside "Other Expenses".
            "hdfc_ergo": ("room rent proportionate deduction", "B.1.1.1"),
            # Niva Bupa caps by room category, not per day, so it is asked in
            # its own vocabulary - see the note in CLAUDE.md.
            "niva_bupa": ("room category higher than eligible pro-rated portion", "6.2.4"),
        }
        for policy, (query, clause_id) in expected.items():
            with self.subTest(policy=policy):
                results = search(query, policy)
                self.assertTrue(results, f"nothing retrieved for {policy}")
                self.assertEqual(results[0].clause.clause_id, clause_id)
                self.assertGreater(results[0].score, 0.8)

    def test_rank_one_is_right_even_when_the_query_is_vague(self):
        """Score tracks query specificity; the ranking should not.

        "higher room category pro-rata deduction" scores 0.58 against Niva Bupa
        while a fuller phrasing scores 0.98 - but 6.2.4 comes first either way.
        Guardrail 5 keys off the score, so a vague query can trigger a false
        abstention. That is the agent's problem to solve by rewriting, not the
        retriever's.
        """
        from core.retrieve import search

        results = search("higher room category pro-rata deduction", "niva_bupa")
        self.assertEqual(results[0].clause.clause_id, "6.2.4")

    def test_results_never_cross_policies(self):
        """A citation from the wrong policy is a fabricated citation."""
        from core.retrieve import search

        for policy in ("star_health", "hdfc_ergo", "niva_bupa"):
            for result in search("room rent limit", policy):
                self.assertEqual(result.clause.policy, policy)

    def test_returns_at_most_top_n(self):
        from core.retrieve import search

        self.assertLessEqual(len(search("room rent", "hdfc_ergo")), settings.rerank_top_n)

    def test_scores_are_ordered_best_first(self):
        from core.retrieve import search

        scores = [r.score for r in search("co-payment percentage", "star_health")]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
