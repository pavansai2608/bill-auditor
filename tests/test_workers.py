"""The per-line worker pool.

Lines were judged one at a time until the numbers made the cost obvious: a
ten-line bill on Groq is ten sequential 6s round trips, and almost all of each
one is spent waiting on a socket. These tests pin the three properties that
make running them at once safe rather than merely faster.
"""

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from core import audit, llm, retrieve
from core.config import settings
from core.models import BillLine


def _lines(count: int) -> list[BillLine]:
    return [BillLine(item=f"item {i}", amount=100.0 * (i + 1), qty=1) for i in range(count)]


class WorkerCountTest(unittest.TestCase):
    """Two, measured, and the same on both backends.

    The first version returned 4 on Groq on the theory that the free tier's 30
    requests a minute was the binding constraint. B01 says otherwise: 222.6s at
    one worker, 175.1s at two, 170.6s at four. The fourth worker buys 2.6% and
    puts the token bucket to sleep for 37s.
    """

    def setUp(self):
        self.addCleanup(setattr, settings, "audit_workers", settings.audit_workers)
        self.addCleanup(llm.reset_client)

    def test_groq_gets_two(self):
        settings.audit_workers = 0
        llm.use_backend("groq")
        self.assertEqual(audit.worker_count(), 2)

    def test_ollama_gets_two_as_well(self):
        """The backends differ in why, not in the number.

        Groq is bounded by retrieval saturating the box; Ollama is bounded by
        retrieval *and* by competing with the reranker for the same cores.
        Both land on two.
        """
        settings.audit_workers = 0
        llm.use_backend("ollama")
        self.assertEqual(audit.worker_count(), 2)

    def test_an_explicit_setting_wins(self):
        settings.audit_workers = 1
        llm.use_backend("groq")
        self.assertEqual(audit.worker_count(), 1)


class ResultsKeepBillOrderTest(unittest.TestCase):
    """The slowest line finishing last must not move it down the report.

    Without this the rows reshuffle between runs, which makes a diff of two
    audits unreadable and the eval flaky for reasons that have nothing to do
    with the model.
    """

    def test_reversed_completion_order_still_reports_in_order(self):
        lines = _lines(6)

        def judge(line: BillLine) -> str:
            # Later lines finish first, so completion order is the reverse of
            # bill order - the exact case an append-as-they-land loop gets wrong.
            time.sleep(0.05 * (len(lines) - int(line.item.split()[1])))
            return line.item

        got = audit._judge_every_line(lines, judge, 6, None)
        self.assertEqual(got, [line.item for line in lines])

    def test_one_worker_and_many_agree(self):
        lines = _lines(8)
        serial = audit._judge_every_line(lines, lambda line: line.amount, 1, None)
        parallel = audit._judge_every_line(lines, lambda line: line.amount, 4, None)
        self.assertEqual(serial, parallel)


class ProgressCountsCompletionsTest(unittest.TestCase):
    """Counting dispatches would show 10 of 10 a second in, then stall."""

    def test_the_counter_climbs_once_per_finished_line(self):
        seen: list[tuple[int, int]] = []
        lock = threading.Lock()

        def record(done: int, total: int) -> None:
            with lock:
                seen.append((done, total))

        audit._judge_every_line(_lines(5), lambda line: time.sleep(0.02), 4, record)

        self.assertEqual(len(seen), 5)
        self.assertEqual([done for done, _ in seen], [1, 2, 3, 4, 5])
        self.assertEqual({total for _, total in seen}, {5})


class LinesActuallyOverlapTest(unittest.TestCase):
    """A pool that never runs two lines at once is a slow sequential loop."""

    def test_retrieval_is_warmed_before_any_worker_starts(self):
        """The models must be built on one thread, or macOS exits 139.

        Judging line one synchronously is not enough: B01's first line is a
        non-payable item that settles without searching, so nothing loads.
        `audit_lines` warms explicitly instead, and only when it is about to
        run more than one worker.
        """
        warmed = []
        with (
            mock.patch.object(
                audit, "_warm_retrieval", side_effect=lambda p, **kw: warmed.append(p)
            ),
            mock.patch.object(audit, "worker_count", return_value=2),
        ):
            audit._warm_retrieval("star_health", use_agent=True)
        self.assertEqual(warmed, ["star_health"])

    def test_a_failed_warm_up_does_not_fail_the_audit(self):
        """A warm-up is an optimisation. It must never be the thing that
        breaks an audit that would otherwise have worked."""
        with mock.patch.object(audit, "search", side_effect=RuntimeError("no index")):
            audit._warm_retrieval("star_health", use_agent=False)

    def test_four_workers_overlap(self):
        live = 0
        peak = 0
        lock = threading.Lock()

        def judge(line: BillLine) -> None:
            nonlocal live, peak
            with lock:
                live += 1
                peak = max(peak, live)
            time.sleep(0.05)
            with lock:
                live -= 1

        audit._judge_every_line(_lines(8), judge, 4, None)
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 4)

    def test_one_worker_never_overlaps(self):
        """The sequential path has to stay reachable: it is the baseline the
        parallel numbers are compared against."""
        live = 0
        peak = 0

        def judge(line: BillLine) -> None:
            nonlocal live, peak
            live += 1
            peak = max(peak, live)
            live -= 1

        audit._judge_every_line(_lines(4), judge, 1, None)
        self.assertEqual(peak, 1)


class AFailedLineStillFailsTheAuditTest(unittest.TestCase):
    """Swallowing a worker exception would turn a broken audit into a quiet
    one, which is the failure mode this whole project exists to avoid."""

    def test_the_exception_reaches_the_caller(self):
        def judge(line: BillLine) -> None:
            if line.item == "item 2":
                raise ValueError("no clause")

        with self.assertRaises(ValueError):
            audit._judge_every_line(_lines(5), judge, 4, None)


class OneVectorStoreNoMatterHowManyThreadsTest(unittest.TestCase):
    """The bug the worker pool found on its very first run.

    `lru_cache` is not atomic. Four workers issued four searches, all four
    missed the same empty cache, and each opened its own Chroma client on the
    same directory. The result was not a slow audit but a 500:

        AttributeError: 'RustBindingsAPI' object has no attribute 'bindings'
        ValueError: Could not connect to tenant default_tenant

    It was unreachable while lines were judged one at a time, which is why
    three years of sequential runs never saw it.
    """

    def setUp(self):
        retrieve._build_vector_store.cache_clear()
        self.addCleanup(retrieve._build_vector_store.cache_clear)

    def test_sixteen_threads_build_exactly_one_client(self):
        built = []

        def slow_chroma(**kwargs):
            # The window matters: constructing Chroma is slow, which is what
            # gives every thread time to miss the cache before any of them
            # fills it.
            time.sleep(0.05)
            built.append(1)
            return object()

        with (
            mock.patch("langchain_chroma.Chroma", side_effect=slow_chroma),
            ThreadPoolExecutor(max_workers=16) as pool,
        ):
            stores = list(pool.map(lambda _: retrieve.get_vector_store(), range(16)))

        self.assertEqual(len(built), 1, "one client, however many threads asked for it")
        self.assertEqual(len({id(s) for s in stores}), 1, "and everyone got the same one")


if __name__ == "__main__":
    unittest.main()
