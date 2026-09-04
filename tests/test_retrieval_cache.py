"""Searches kept on disk, and the one thing that must never come back from them.

The in-memory cache in `core/retrieve.py` dies with the process. Retrieval is
the other 90% of an audit, so after a restart a bill that has been audited
before still costs a full re-search: with every model call served from
`data/llm_cache`, re-running one 10-line bill cost 94.6s of searching and 68s
of wall clock. This cache is what removes that.

**The failure it must not have** is a hit that returns a `clause_id` the index
no longer contains. Nothing downstream would catch it: `search()` looks the id
up in the live index, so a stale id becomes a dropped result at best and a
citation pointing at the wrong clause at worst. The key carries a sha256 of
`clauses.json`, so re-indexing does not make entries stale - it makes them
unaddressable, which is a stronger guarantee than invalidation. That is the
first test below, and it is the reason this file exists.

Two more rules the key has to keep:

* **Policies never share an entry.** Two policies asking the same question are
  two lookups; a hit that crossed them would be a fabricated citation of the
  worst kind, which is the one thing this project cannot ship.
* **The stored entry holds the text, not just the ids.** If it held ids alone
  and re-read the clause text at hit time, a clause edited since would come
  back as a stale id wearing fresh text - a citation that looks right and
  quotes something the judge never saw.

Nothing here loads a model. The retriever is a stub and the cache directory is
a temporary one, so the suite stays offline and never touches `data/`.
"""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from langchain_core.documents import Document

from core import cache, retrieve
from core.config import Settings, settings


def documents(*pairs: tuple[str, str]) -> list[Document]:
    """One document per (clause_id, text), shaped like a reranked window."""
    return [
        Document(
            page_content=text,
            metadata={"clause_id": clause_id, "policy": "star_health", "relevance_score": 0.9},
        )
        for clause_id, text in pairs
    ]


DEFAULT = documents(
    ("II.1", "In-patient Treatment. Room rent up to Rs 5,000/- per day."),
    ("I.Def45", "Associated Medical Expenses means nursing charges, surgeon fees..."),
)


class StubRetriever:
    """Counts what actually reached the retriever, which is the whole point."""

    def __init__(self, result: list[Document] | None = None) -> None:
        self.calls: list[str] = []
        self.result = DEFAULT if result is None else result

    def invoke(self, query: str) -> list[Document]:
        self.calls.append(query)
        return self.result


class DiskCacheTest(unittest.TestCase):
    def setUp(self):
        # The index sits beside the cache, not inside it, so clearing one
        # cannot touch the other.
        root = Path(tempfile.mkdtemp(prefix="ba-retrieval-"))
        self.dir = root / "retrieval_cache"
        self.dir.mkdir()
        self.index = root / "clauses.json"
        self.write_index([{"clause_id": "II.1"}])

        for name, value in (
            ("retrieval_cache_dir", self.dir),
            ("clauses_path", self.index),
        ):
            patch = mock.patch.object(
                Settings, name, new_callable=mock.PropertyMock, return_value=value
            )
            patch.start()
            self.addCleanup(patch.stop)

        retrieve.clear_search_cache()
        self.addCleanup(retrieve.clear_search_cache)
        cache.forget_file_digests()
        self.addCleanup(cache.forget_file_digests)
        self.stats = dict(retrieve.RETRIEVAL_DISK_STATS)
        self.addCleanup(retrieve.RETRIEVAL_DISK_STATS.update, self.stats)
        # The memory layer would answer before disk ever did, and these tests
        # are about disk. Each test that wants both says so explicitly.
        self.without_memory()

    def without_memory(self):
        patch = mock.patch.object(settings, "retrieval_cache_size", 0)
        patch.start()
        self.addCleanup(patch.stop)

    def write_index(self, clauses: list[dict]) -> None:
        self.index.write_text(json.dumps(clauses), encoding="utf-8")
        cache.forget_file_digests()

    def stored(self) -> list[Path]:
        return sorted(self.dir.glob("*.json"))

    def retrieve_twice(self, query="room rent limit", policy="star_health", result=None):
        stub = StubRetriever(result)
        with mock.patch.object(retrieve, "get_retriever", return_value=stub):
            first = retrieve._retrieve_documents(query, policy)
            second = retrieve._retrieve_documents(query, policy)
        return stub, first, second


class AReindexMakesEveryEntryUnaddressableTest(DiskCacheTest):
    """The reason this cache is allowed to exist at all.

    A stored search holds clause ids. If the index is rebuilt and those ids
    move or vanish, serving the old answer would cite a clause that is no
    longer there. The digest in the key means the old entry is never looked up
    again rather than being looked up and found wrong.
    """

    def test_mutating_clauses_json_turns_the_next_lookup_into_a_miss(self):
        stub = StubRetriever()
        with mock.patch.object(retrieve, "get_retriever", return_value=stub):
            retrieve._retrieve_documents("room rent limit", "star_health")
            retrieve._retrieve_documents("room rent limit", "star_health")
            self.assertEqual(1, len(stub.calls), "the second lookup came from disk")

            self.write_index([{"clause_id": "II.1"}, {"clause_id": "II.7"}])
            retrieve._retrieve_documents("room rent limit", "star_health")

        self.assertEqual(2, len(stub.calls), "a rebuilt index must not be answered from disk")

    def test_the_old_entry_is_left_alone_rather_than_served(self):
        """Unaddressable, not deleted. Reverting the index makes it valid again."""
        stub = StubRetriever()
        with mock.patch.object(retrieve, "get_retriever", return_value=stub):
            retrieve._retrieve_documents("room rent limit", "star_health")
            before = {p.name for p in self.stored()}

            self.write_index([{"clause_id": "II.9"}])
            retrieve._retrieve_documents("room rent limit", "star_health")
            self.assertEqual(2, len(self.stored()), "the new index wrote its own entry")

            self.write_index([{"clause_id": "II.1"}])
            retrieve._retrieve_documents("room rent limit", "star_health")

        self.assertEqual(2, len(stub.calls), "the original entry is addressable again")
        self.assertTrue(before <= {p.name for p in self.stored()})

    def test_the_index_digest_is_in_the_key(self):
        first = retrieve.disk_cache_key("room rent limit", "star_health")
        self.write_index([{"clause_id": "II.1"}, {"clause_id": "II.2"}])
        self.assertNotEqual(first, retrieve.disk_cache_key("room rent limit", "star_health"))


class TheKeySeparatesWhatMustBeSeparateTest(DiskCacheTest):
    def test_two_policies_are_two_lookups(self):
        """A hit that crossed policies would be a fabricated citation."""
        stub = StubRetriever()
        with mock.patch.object(retrieve, "get_retriever", return_value=stub):
            retrieve._retrieve_documents("room rent limit", "star_health")
            retrieve._retrieve_documents("room rent limit", "niva_bupa")
        self.assertEqual(2, len(stub.calls))
        self.assertEqual(2, len(self.stored()))

    def test_the_query_is_used_exactly_as_sent(self):
        keys = {
            retrieve.disk_cache_key(query, "star_health")
            for query in ("room rent limit", "Room Rent Limit", " room rent limit", "room  rent")
        }
        self.assertEqual(4, len(keys), "nothing about the query may be normalised away")

    def test_retriever_config_that_changes_the_result_changes_the_key(self):
        base = retrieve.disk_cache_key("room rent limit", "star_health")
        for name, value in (
            ("chroma_top_k", 10),
            ("bm25_top_k", 10),
            ("dense_weight", 0.5),
            ("sparse_weight", 0.5),
            ("embedding_model", "BAAI/bge-small-en-v1.5"),
            ("reranker_model", "BAAI/bge-reranker-large"),
            ("rerank_top_n", 5),
        ):
            with self.subTest(setting=name), mock.patch.object(settings, name, value):
                self.assertNotEqual(
                    base,
                    retrieve.disk_cache_key("room rent limit", "star_health"),
                    f"{name} changes what comes back and must change the key",
                )

    def test_the_sub_chunk_sizes_are_in_the_key_too(self):
        """Constants rather than settings, but they decide how clauses are cut."""
        base = retrieve.disk_cache_key("room rent limit", "star_health")
        with mock.patch.object(retrieve, "SUB_CHUNK_TARGET", 900):
            self.assertNotEqual(base, retrieve.disk_cache_key("room rent limit", "star_health"))

    def test_it_hashes_the_same_way_the_llm_cache_does(self):
        """One serialisation, so the two caches cannot drift apart."""
        self.assertEqual(
            cache.key_digest({"b": 2, "a": 1}),
            cache.key_digest({"a": 1, "b": 2}),
        )


class WhatIsStoredTest(DiskCacheTest):
    def test_an_entry_holds_the_ids_and_the_text_that_was_scored(self):
        self.retrieve_twice()
        entry = json.loads(self.stored()[0].read_text(encoding="utf-8"))
        self.assertEqual(["II.1", "I.Def45"], [row["clause_id"] for row in entry["documents"]])
        self.assertIn("Rs 5,000/- per day", entry["documents"][0]["page_content"])
        self.assertEqual("star_health", entry["policy"])
        self.assertEqual("room rent limit", entry["query"])

    def test_a_hit_returns_the_stored_text_not_a_fresh_read_of_the_clause(self):
        _, first, second = self.retrieve_twice()
        self.assertEqual(
            [(d.metadata["clause_id"], d.page_content) for d in first],
            [(d.metadata["clause_id"], d.page_content) for d in second],
        )

    def test_the_rerank_score_survives_the_round_trip(self):
        """`search()` reads relevance_score off the metadata; guardrail 5 keys on it."""
        _, _, second = self.retrieve_twice()
        self.assertEqual([0.9, 0.9], [d.metadata["relevance_score"] for d in second])

    def test_an_empty_result_is_stored_and_served(self):
        stub, _, second = self.retrieve_twice(result=[])
        self.assertEqual(1, len(stub.calls), "finding nothing is an answer worth keeping")
        self.assertEqual([], second)


class ItSurvivesAndItIsSafeTest(DiskCacheTest):
    def test_the_memory_layer_answers_first_and_disk_answers_after_a_restart(self):
        with mock.patch.object(settings, "retrieval_cache_size", 512):
            stub = StubRetriever()
            with mock.patch.object(retrieve, "get_retriever", return_value=stub):
                retrieve._retrieve_documents("room rent limit", "star_health")
                retrieve._retrieve_documents("room rent limit", "star_health")
                self.assertEqual(1, len(stub.calls))

                # What a restart does: the process forgets, the disk does not.
                retrieve.clear_search_cache()
                retrieve._retrieve_documents("room rent limit", "star_health")

            self.assertEqual(1, len(stub.calls), "the restart was answered from disk")

    def test_turning_it_off_stops_both_reading_and_writing(self):
        with mock.patch.object(settings, "retrieval_cache_enabled", False):
            stub, _, _ = self.retrieve_twice()
        self.assertEqual(2, len(stub.calls))
        self.assertEqual([], self.stored())

    def test_a_half_written_entry_is_a_miss_and_not_a_crash(self):
        key = retrieve.disk_cache_key("room rent limit", "star_health")
        (self.dir / f"{key}.json").write_text("{ half a file", encoding="utf-8")
        self.assertIsNone(retrieve.disk_cache_get(key))
        self.assertEqual([], self.stored(), "the bad entry is discarded, not left to fail again")

    def test_an_entry_from_an_older_shape_of_this_code_is_discarded(self):
        key = retrieve.disk_cache_key("room rent limit", "star_health")
        (self.dir / f"{key}.json").write_text(
            json.dumps({"key": key, "documents": [{"clause_id": "II.1"}]}), encoding="utf-8"
        )
        self.assertIsNone(retrieve.disk_cache_get(key))
        self.assertEqual([], self.stored())

    def test_many_threads_writing_one_key_never_raise(self):
        """The race the LLM cache had. It must not come back in the second cache."""
        key = retrieve.disk_cache_key("room rent limit", "star_health")
        big = documents(("II.1", "x" * 200_000))
        failures: list[str] = []

        def write() -> None:
            for _ in range(30):
                try:
                    retrieve.disk_cache_put(key, big, query="q", policy="star_health")
                except Exception as exc:
                    failures.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=write) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual([], failures[:5], f"{len(failures)} concurrent writes failed")
        self.assertEqual([], list(self.dir.glob("*.tmp")), "a temp file was orphaned")
        self.assertEqual(1, len(retrieve.disk_cache_get(key)))

    def test_health_reports_what_the_process_resolved(self):
        self.retrieve_twice()
        health = retrieve.cache_health()
        self.assertTrue(health["enabled"])
        self.assertEqual(str(self.dir), health["dir"])
        self.assertTrue(health["writable"])
        self.assertGreaterEqual(health["entries"], 1)

    def test_clearing_it_removes_the_stored_searches(self):
        self.retrieve_twice()
        self.assertEqual(1, len(self.stored()))
        self.assertEqual(1, retrieve.clear_disk_cache())
        self.assertEqual([], self.stored())
        self.assertTrue(self.index.exists(), "clearing the cache is not clearing the index")


if __name__ == "__main__":
    unittest.main()
