"""Checkpointing the eval, and the guards that stop it lying.

A 44-bill run died at bill 38 and lost 37 completed bills. Saving them is the
easy half; the hard half is making sure a saved result can never be counted
against inputs it was not produced from, and that a run which did not finish
never writes a row.
"""

import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "eval"))

import checkpoint as cp

ROOT = Path(__file__).resolve().parents[1]

from core.models import AuditReport, LineVerdict


def a_report() -> AuditReport:
    return AuditReport(
        lines=[
            LineVerdict(
                item="surgeon fee",
                charged=80000.0,
                allowed=80000.0,
                clause_id="II.1",
                reason="covered in full",
            )
        ],
        total_charged=80000.0,
        total_allowed=80000.0,
        flagged_count=0,
        policy="star_health",
        trace=[{"node": "summary", "item": "surgeon fee", "attempts": 1}],
    )


def a_checkpoint(**over) -> cp.Checkpoint:
    fields = {
        "bill_id": "B01",
        "report": a_report(),
        "elapsed": 12.5,
        "tool_calls": 7,
        "backend": "ollama",
        "model": "qwen3:8b",
        "bill_hash": "billhash",
        "key_hash": "keyhash",
        "fingerprint": "codeprint",
    }
    fields.update(over)
    return cp.Checkpoint(**fields)


class CheckpointRoundTripTest(unittest.TestCase):
    """The stored result has to rebuild the row, not just prove work happened."""

    def setUp(self):
        self.tmp = pathlib.Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        patch = mock.patch.object(cp, "RUNS_DIR", self.tmp)
        patch.start()
        self.addCleanup(patch.stop)

    def test_a_saved_bill_comes_back_unchanged(self):
        cp.save("v5-full", a_checkpoint())
        got = cp.load(
            "v5-full", "B01", bill_hash="billhash", key_hash="keyhash", fingerprint="codeprint"
        )

        self.assertIsNotNone(got)
        self.assertEqual(got.report.total_allowed, 80000.0)
        self.assertEqual(got.report.lines[0].clause_id, "II.1")
        self.assertEqual(got.tool_calls, 7)
        self.assertEqual(got.elapsed, 12.5)
        # Which model answered is part of the result, not metadata about it.
        self.assertEqual(got.backend, "ollama")
        self.assertEqual(got.model, "qwen3:8b")

    def test_the_trace_survives(self):
        """`render` reads attempts and fast-path counts out of the trace."""
        cp.save("v5-full", a_checkpoint())
        got = cp.load(
            "v5-full", "B01", bill_hash="billhash", key_hash="keyhash", fingerprint="codeprint"
        )
        self.assertEqual(got.report.trace[0]["attempts"], 1)

    def test_versions_do_not_share_results(self):
        cp.save("v5-full", a_checkpoint())
        self.assertIsNone(
            cp.load("v6", "B01", bill_hash="billhash", key_hash="keyhash", fingerprint="codeprint")
        )


class AStaleCheckpointIsRefusedTest(unittest.TestCase):
    """The reason the hashes exist.

    A checkpoint that still counts after its inputs changed is not a saving,
    it is a score describing a bill that no longer exists.
    """

    def setUp(self):
        self.tmp = pathlib.Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        patch = mock.patch.object(cp, "RUNS_DIR", self.tmp)
        patch.start()
        self.addCleanup(patch.stop)
        cp.save("v5-full", a_checkpoint())

    def test_a_changed_bill_invalidates_it(self):
        got = cp.load(
            "v5-full",
            "B01",
            bill_hash="the bill was edited",
            key_hash="keyhash",
            fingerprint="codeprint",
        )
        self.assertIsNone(got)

    def test_a_changed_answer_key_entry_invalidates_it(self):
        got = cp.load(
            "v5-full",
            "B01",
            bill_hash="billhash",
            key_hash="the key was edited",
            fingerprint="codeprint",
        )
        self.assertIsNone(got)

    def test_an_older_format_is_refused(self):
        path = cp.path_for("v5-full", "B01", "codeprint")
        raw = json.loads(path.read_text())
        raw["format"] = cp.FORMAT - 1
        path.write_text(json.dumps(raw))
        self.assertIsNone(
            cp.load(
                "v5-full", "B01", bill_hash="billhash", key_hash="keyhash", fingerprint="codeprint"
            )
        )

    def test_a_truncated_file_is_refused_rather_than_raising(self):
        """The failure being defended against is a process dying mid-write."""
        cp.path_for("v5-full", "B01", "codeprint").write_text('{"format": 2, "bill_id": "B0')
        self.assertIsNone(
            cp.load(
                "v5-full", "B01", bill_hash="billhash", key_hash="keyhash", fingerprint="codeprint"
            )
        )

    def test_clear_removes_them(self):
        self.assertEqual(cp.clear("v5-full"), 1)
        self.assertIsNone(
            cp.load(
                "v5-full", "B01", bill_hash="billhash", key_hash="keyhash", fingerprint="codeprint"
            )
        )


class DigestIsStableTest(unittest.TestCase):
    def test_key_order_does_not_matter(self):
        """A dict that round-trips through JSON in another order is the same
        answer key entry, and must not invalidate a run."""
        self.assertEqual(
            cp.digest({"a": 1, "b": [1, 2]}),
            cp.digest({"b": [1, 2], "a": 1}),
        )

    def test_a_changed_value_changes_the_digest(self):
        self.assertNotEqual(cp.digest({"allowed": 5000}), cp.digest({"allowed": 5001}))


class VersionLabelsCannotEscapeTheCacheTest(unittest.TestCase):
    """A version label reaches the filesystem."""

    def test_a_traversing_label_is_flattened(self):
        directory = cp.run_dir("../../etc/v5")
        self.assertNotIn("..", directory.parts)
        self.assertTrue(str(directory).startswith(str(cp.RUNS_DIR)))


class TheRunnerReusesACheckpointTest(unittest.TestCase):
    """The saving, and the guard on it, at the level `main` actually uses.

    `score_bill` must audit nothing when handed a checkpoint, and must fold the
    stored report into the tallies exactly as if it had just produced it.
    """

    def setUp(self):
        import evaluate

        self.evaluate = evaluate

    def _expected(self) -> dict:
        return {
            "policy": "star_health",
            "sum_insured": 300000.0,
            "category": "clean",
            "lines": [
                {
                    "item": "surgeon fee",
                    "charged": 80000.0,
                    "qty": 1,
                    "allowed": 80000.0,
                    "clause_id": "II.1",
                }
            ],
        }

    def test_a_checkpoint_is_folded_in_without_auditing(self):
        run = self.evaluate.Run()
        with mock.patch.object(
            self.evaluate, "audit_one", side_effect=AssertionError("must not audit")
        ):
            self.evaluate.score_bill("B01", self._expected(), {"II.1"}, run, done=a_checkpoint())

        self.assertEqual(run.bills_run, 1)
        self.assertEqual(run.overall.lines_scored, 1)
        self.assertEqual(run.overall.amount_right, 1, "the stored amount still scores")
        self.assertEqual(run.overall.citation_right, 1, "the stored citation still scores")
        self.assertEqual(run.overall.fabricated, 0)
        self.assertEqual(run.latencies, [12.5], "the original timing is kept, not re-measured")
        self.assertEqual(run.tool_calls, [7])

    def test_without_a_checkpoint_it_audits(self):
        run = self.evaluate.Run()
        with mock.patch.object(self.evaluate, "audit_one", return_value=a_checkpoint()) as audited:
            self.evaluate.score_bill("B01", self._expected(), {"II.1"}, run)
        audited.assert_called_once()
        self.assertEqual(run.overall.amount_right, 1)


class PartialRunsDoNotWriteARowTest(unittest.TestCase):
    """A row is a claim, and it has to say what it is a claim about.

    Two different things used to be refused together. A run that *crashed*
    part-way through its selection must never be recorded - the number would be
    indistinguishable from a finished one. A run that deliberately narrows the
    selection is a different case: `--quick` is what the Jenkins Eval stage
    runs, and a gate needs a recorded quick-subset figure to compare against.

    So a narrowed run is recorded and carries its scope in the row; an
    unfinished one is still refused.
    """

    def setUp(self):
        import evaluate

        self.evaluate = evaluate

    def _run(self, argv: list[str], written: list, *, finishes: bool = True):
        """Run main() with the audit stubbed out.

        `finishes` is the whole point of the class: when True the stub counts
        each bill as scored, which is a run that completed its selection; when
        False it counts none, which is what a crash looks like to the guard.
        """

        def scored(bill_id, expected, valid_ids, run, *args, **kwargs):
            if finishes:
                run.bills_run += 1
                # A run with no scored line reports "nothing to score" and
                # returns before writing, so the stub has to look like it did
                # some work or the guard under test is never reached.
                run.overall.lines_scored += 1
                run.overall.amount_right += 1

        with (
            mock.patch.object(sys, "argv", ["evaluate.py", *argv]),
            mock.patch.object(self.evaluate, "write_results", side_effect=written.append),
            mock.patch.object(self.evaluate, "score_bill", side_effect=scored),
        ):
            return self.evaluate.main()

    def test_a_narrowed_run_records_its_scope(self):
        """--bills is complete for what it selected, and says so in the row."""
        written: list[str] = []
        code = self._run(["--bills", "B01", "--write", "--version", "test-partial"], written)
        self.assertEqual(code, 0)
        self.assertEqual(len(written), 1)
        self.assertIn("Scope: 1 of", written[0])
        self.assertIn("--bills selection", written[0])
        self.assertIn("Not a whole-set number", written[0])

    def test_quick_records_its_scope(self):
        """The Jenkins gate depends on this row existing."""
        written: list[str] = []
        code = self._run(["--quick", "--write", "--version", "test-quick"], written)
        self.assertEqual(code, 0)
        self.assertEqual(len(written), 1)
        self.assertIn("--quick subset", written[0])
        self.assertIn("Not a whole-set number", written[0])

    def test_a_full_run_carries_no_scope_banner(self):
        """The banner marks a narrowed run; a whole-set row must not wear it."""
        written: list[str] = []
        code = self._run(["--write", "--version", "test-full"], written)
        self.assertEqual(code, 0)
        self.assertEqual(len(written), 1)
        self.assertNotIn("Scope:", written[0])

    def test_a_run_that_did_not_finish_its_selection_is_still_refused(self):
        """The crashed-run case, which is what the guard is really for."""
        written: list[str] = []
        code = self._run(["--write", "--version", "test-crashed"], written, finishes=False)
        self.assertEqual(code, 4)
        self.assertEqual(written, [], "an unfinished run must not be recorded")


class TheFingerprintDecidesWhatCanBeReplayedTest(unittest.TestCase):
    """A checkpoint is only valid for the code that produced it.

    This is the bug the fingerprint exists to close. Jenkins keeps its
    workspace, so the checkpoints survive between builds; with only the inputs
    hashed, a commit that damaged the auditor replayed the previous build's
    reports and the Eval stage passed in one second. The gate failed at exactly
    the job it exists to do.
    """

    def setUp(self):
        cp.RUNS_DIR = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, cp.RUNS_DIR, ignore_errors=True)
        cp.save("v7", a_checkpoint())

    def load(self, fingerprint):
        return cp.load(
            "v7", "B01", bill_hash="billhash", key_hash="keyhash", fingerprint=fingerprint
        )

    def test_the_same_code_replays(self):
        """The saving is real and must survive an unrelated commit."""
        self.assertIsNotNone(self.load("codeprint"))

    def test_changed_code_is_refused(self):
        """The important one. A different fingerprint must recompute the bill."""
        self.assertIsNone(self.load("a different build of the auditor"))

    def test_the_fingerprint_is_stored_not_only_compared(self):
        """A stored result should say which code produced it."""
        raw = json.loads(cp.path_for("v7", "B01", "codeprint").read_text())
        self.assertEqual(raw["fingerprint"], "codeprint")


class WhatTheFingerprintCoversTest(unittest.TestCase):
    """Which edits invalidate a run, and which must not."""

    def test_editing_the_audit_path_changes_it(self):
        """QUERY_ANGLES is in core/agent.py, and it decides what is retrieved."""
        before = cp.code_digest()
        target = cp.AUDIT_SOURCE_DIR / "agent.py"
        original = target.read_bytes()
        try:
            target.write_bytes(original.replace(b'"{item} limit coverage"', b'"policy"'))
            cp.code_digest.cache_clear()
            self.assertNotEqual(before, cp.code_digest())
        finally:
            target.write_bytes(original)
            cp.code_digest.cache_clear()
        self.assertEqual(before, cp.code_digest(), "restoring the file restores the digest")

    def test_a_file_outside_the_audit_path_does_not(self):
        """A 40-minute run must not be thrown away by an unrelated commit."""
        before = cp.code_digest()
        stray = ROOT / "eval" / ".fingerprint_probe.txt"
        stray.write_text("not part of the audit")
        try:
            cp.code_digest.cache_clear()
            self.assertEqual(before, cp.code_digest())
        finally:
            stray.unlink(missing_ok=True)
            cp.code_digest.cache_clear()

    def test_the_run_flags_are_part_of_it(self):
        """--second-pass rewrites every associated line; it cannot be ignored."""
        plain = cp.fingerprint(use_agent=True, second_pass=False)
        second = cp.fingerprint(use_agent=True, second_pass=True)
        naive = cp.fingerprint(use_agent=False, second_pass=False)
        self.assertNotEqual(plain, second)
        self.assertNotEqual(plain, naive)


if __name__ == "__main__":
    unittest.main()
