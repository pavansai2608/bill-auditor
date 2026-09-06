"""The disk cache in front of the model, and the one race it used to lose.

Two questions this file answers, because both were asked of a live system that
appeared to re-run the same audit from scratch every time:

* Does an identical audit produce identical cache keys? Nothing that varies
  between two runs of the same bill - a clock, a job id, a request id - may
  reach the key payload, or every repeat is a miss and the cache is decoration.
* Can two audit workers write the same key at once? They can, and until this
  was fixed the loser raised FileNotFoundError out of `cache_put` and took its
  bill line down with it. `audit_workers` resolves to 2 on both backends, and
  a bill with two identical lines is ordinary.

Nothing here calls a model. The cache is exercised directly, against a
temporary directory, so the suite stays offline.
"""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from core import cache, llm
from core.config import Settings, settings

# The exact key the shared serialisation produces for a fixed payload. Every
# entry already on disk was addressed with this dump, so a change to
# `core.cache.canonical` would orphan thousands of cached answers in silence.
# If this assertion ever has to move, the caches have to be rebuilt with it.
PINNED_PAYLOAD = {"backend": "ollama", "model": "qwen3:8b", "messages": [{"role": "human", "n": 1}]}
PINNED_KEY = "50494a5c2b39067dccdcefc2f3d11be0db492da0afb9f4da1eb55c857b417d5a"


class CacheDirTest(unittest.TestCase):
    """Every test in this file writes to a temporary cache, never data/."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="ba-cache-"))
        patch = mock.patch.object(
            Settings, "llm_cache_dir", new_callable=mock.PropertyMock, return_value=self.dir
        )
        patch.start()
        self.addCleanup(patch.stop)
        llm.reset_client()
        self.addCleanup(llm.reset_client)
        self.stats = dict(llm.CACHE_STATS)
        self.addCleanup(llm.CACHE_STATS.update, self.stats)

    def entries(self) -> list[Path]:
        return sorted(self.dir.glob("*.json"))

    def leftovers(self) -> list[Path]:
        return sorted(self.dir.glob("*.tmp"))


class ConcurrentWritersTest(CacheDirTest):
    """Six threads, one key. Before the fix this failed 153 times in 240."""

    def test_writing_one_key_from_many_threads_never_raises(self):
        key = "a" * 64
        # Big enough that a shared temp file is still being written when the
        # next thread truncates it, which is what made the race reachable.
        response = {"clause_id": "II.1", "confident": True, "reasoning": "x" * 200_000}
        failures: list[str] = []

        def write() -> None:
            for _ in range(40):
                try:
                    llm.cache_put(key, response, {"kind": "structured", "schema": "JudgeOutput"})
                except Exception as exc:  # the bug was FileNotFoundError
                    failures.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=write) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual([], failures[:5], f"{len(failures)} concurrent writes failed")

    def test_the_entry_left_behind_is_whole(self):
        """Interleaved writers used to leave a half-file that read back as a miss."""
        key = "b" * 64
        response = {"clause_id": "II.7", "confident": True, "reasoning": "y" * 200_000}

        def write() -> None:
            for _ in range(20):
                llm.cache_put(key, response, {"kind": "structured", "schema": "JudgeOutput"})

        threads = [threading.Thread(target=write) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(1, len(self.entries()), "one key, one file")
        entry = json.loads(self.entries()[0].read_text(encoding="utf-8"))
        self.assertEqual(response, entry["response"])
        self.assertEqual([], self.leftovers(), "a temp file was orphaned")

    def test_a_failed_write_does_not_orphan_its_temp_file(self):
        with (
            mock.patch.object(cache.json, "dump", side_effect=OSError("disk full")),
            self.assertRaises(OSError),
        ):
            llm.cache_put("c" * 64, {"a": 1}, {"kind": "structured"})
        self.assertEqual([], self.leftovers())
        self.assertEqual([], self.entries())


class TheKeyIsStableAcrossRunsTest(CacheDirTest):
    """The premise of the cache: two identical audits ask identical questions.

    A clock, a uuid or a retrieval order that shuffles would each turn every
    repeat into a miss, with nothing visible but a slow page.
    """

    def payload_fields(self) -> set[str]:
        messages = llm._build_messages("judge this line", system="you are a judge")
        with mock.patch.object(cache, "canonical", wraps=cache.canonical) as canonical:
            llm.cache_key(messages, schema_name="JudgeOutput")
        return set(canonical.call_args.args[0])

    def test_the_key_payload_holds_only_things_that_decide_the_answer(self):
        self.assertEqual(
            {
                "backend",
                "model",
                "num_ctx",
                "temperature",
                "reasoning",
                "num_predict",
                "schema",
                "messages",
            },
            self.payload_fields(),
            "a field that varies per run would make every repeat a miss",
        )

    def test_the_serialisation_still_produces_the_key_it_always_has(self):
        """The ~2,000 entries already on disk were addressed with this exact dump."""
        self.assertEqual(PINNED_KEY, cache.key_digest(PINNED_PAYLOAD))
        self.assertEqual(
            cache.key_digest(PINNED_PAYLOAD),
            cache.key_digest(dict(reversed(list(PINNED_PAYLOAD.items())))),
            "field order must not reach the key",
        )

    def test_the_same_prompt_keys_the_same_way_twice(self):
        messages = llm._build_messages("same bill, same policy", system=None)
        first = llm.cache_key(messages, schema_name="JudgeOutput")
        second = llm.cache_key(llm._build_messages("same bill, same policy", None), "JudgeOutput")
        self.assertEqual(first, second)

    def test_a_stored_answer_is_served_back_without_the_model(self):
        messages = llm._build_messages("what is the room rent limit?", system=None)
        key = llm.cache_key(messages, schema_name="JudgeOutput")

        self.assertIsNone(llm.cache_get(key), "nothing stored yet")
        llm.cache_put(key, {"clause_id": "II.1"}, {"kind": "structured"})
        self.assertEqual({"clause_id": "II.1"}, llm.cache_get(key))

    def test_an_unreadable_entry_is_a_miss_and_not_a_crash(self):
        key = "d" * 64
        (self.dir / f"{key}.json").write_text("{ half a file", encoding="utf-8")
        self.assertIsNone(llm.cache_get(key))
        self.assertEqual([], self.entries(), "the bad entry is discarded, not left to fail again")

    def test_the_cache_is_off_when_the_setting_says_so(self):
        with mock.patch.object(settings, "llm_cache_enabled", False):
            llm.cache_put("e" * 64, {"a": 1}, {"kind": "structured"})
            self.assertEqual([], self.entries())
            self.assertIsNone(llm.cache_get("e" * 64))


class CacheHealthTest(CacheDirTest):
    """The one field that settles "why is this slow again", from the process itself."""

    def test_it_reports_the_resolved_setting_not_the_env_file(self):
        with mock.patch.object(settings, "llm_cache_enabled", False):
            self.assertFalse(llm.cache_health()["enabled"])
        with mock.patch.object(settings, "llm_cache_enabled", True):
            self.assertTrue(llm.cache_health()["enabled"])

    def test_it_names_the_directory_and_counts_what_is_in_it(self):
        llm.cache_put("f" * 64, {"a": 1}, {"kind": "structured"})
        health = llm.cache_health()
        self.assertEqual(str(self.dir), health["dir"])
        self.assertTrue(health["writable"])
        self.assertEqual(1, health["entries"])

    def test_a_missing_directory_answers_rather_than_raising(self):
        with mock.patch.object(
            Settings,
            "llm_cache_dir",
            new_callable=mock.PropertyMock,
            return_value=self.dir / "gone",
        ):
            health = llm.cache_health()
        self.assertFalse(health["writable"])
        self.assertEqual(0, health["entries"])


if __name__ == "__main__":
    unittest.main()
