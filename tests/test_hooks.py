"""PyUnit tests for the git hooks. They run the hook scripts, not a copy.

These exist because the commit-msg hook silently did nothing for an entire
build: `core.hooksPath` was never set, and even if it had been, the hook had no
ticket check in it. Both are the kind of failure that produces no error - the
commits just go through.

The tests run the real script in `.githooks/`, so a change to the hook that
breaks a rule fails here rather than three weeks later in a review.
"""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "commit-msg"
PRE_COMMIT = ROOT / ".githooks" / "pre-commit"


def run_hook(message: str) -> subprocess.CompletedProcess:
    """Feed one commit message to the hook exactly as git would."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(message)
        path = handle.name
    try:
        return subprocess.run(
            [str(HOOK), path], capture_output=True, text=True, cwd=ROOT, check=False
        )
    finally:
        Path(path).unlink(missing_ok=True)


class HookIsInstallableTest(unittest.TestCase):
    def test_the_hooks_exist_and_are_executable(self):
        for hook in (HOOK, PRE_COMMIT):
            self.assertTrue(hook.exists(), f"{hook} is missing")
            mode = hook.stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR, f"{hook} is not executable, so git will skip it")


class TicketTest(unittest.TestCase):
    """The check that was missing. A message with no ticket must be rejected."""

    def test_a_message_with_no_ticket_is_rejected(self):
        result = run_hook("feat(api): return a job id and poll instead of blocking")
        self.assertNotEqual(result.returncode, 0, "a message with no ticket must not be accepted")
        self.assertIn("no [BA-XX] ticket", result.stderr)

    def test_the_same_message_with_a_ticket_is_accepted(self):
        result = run_hook("feat(api): return a job id and poll instead of blocking [BA-10]")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_ticket_that_is_not_at_the_end_is_rejected(self):
        result = run_hook("feat(api): [BA-10] return a job id")
        self.assertNotEqual(result.returncode, 0)

    def test_a_ticket_with_no_number_is_rejected(self):
        self.assertNotEqual(run_hook("feat(api): add a thing [BA-]").returncode, 0)

    def test_more_than_two_digits_is_fine(self):
        self.assertEqual(run_hook("feat(api): add a thing [BA-123]").returncode, 0)


class ConventionalCommitTest(unittest.TestCase):
    def test_an_unknown_type_is_rejected(self):
        result = run_hook("wibble(api): add a thing [BA-10]")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a Conventional Commit", result.stderr)

    def test_a_missing_type_is_rejected(self):
        self.assertNotEqual(run_hook("added a thing [BA-10]").returncode, 0)

    def test_every_allowed_type_passes(self):
        for kind in ("feat", "fix", "refactor", "test", "docs", "chore", "perf", "ci", "build"):
            with self.subTest(kind=kind):
                self.assertEqual(run_hook(f"{kind}(core): a change [BA-10]").returncode, 0)

    def test_a_breaking_change_marker_is_allowed(self):
        self.assertEqual(run_hook("feat(api)!: change the shape [BA-10]").returncode, 0)


class SubjectLengthTest(unittest.TestCase):
    def test_a_subject_over_seventy_two_characters_is_rejected(self):
        subject = "feat(api): " + "x" * 60 + " [BA-10]"
        self.assertGreater(len(subject), 72)
        result = run_hook(subject)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("limit is 72", result.stderr)

    def test_the_ticket_counts_towards_the_limit(self):
        # 72 exactly, ticket included.
        subject = "feat(api): " + "x" * 53 + " [BA-10]"
        self.assertEqual(len(subject), 72)
        self.assertEqual(run_hook(subject).returncode, 0)


class ExemptionTest(unittest.TestCase):
    """Messages git writes itself cannot be made to carry a ticket."""

    def test_a_merge_commit_is_let_through(self):
        self.assertEqual(run_hook("Merge branch 'feature/api' into develop").returncode, 0)

    def test_a_revert_is_let_through(self):
        self.assertEqual(run_hook('Revert "feat(api): add a thing [BA-10]"').returncode, 0)

    def test_a_fixup_is_let_through(self):
        # It is squashed into a target whose message already has the ticket.
        self.assertEqual(run_hook("fixup! feat(api): add a thing [BA-10]").returncode, 0)


class BodyTest(unittest.TestCase):
    def test_only_the_subject_is_checked(self):
        message = "feat(api): add a thing [BA-10]\n\nA body line with no ticket in it at all.\n"
        self.assertEqual(run_hook(message).returncode, 0)


if __name__ == "__main__":
    unittest.main()


class SecretsAreBlockedTest(unittest.TestCase):
    """A leaked key cannot be un-leaked by a later commit, so it is stopped here.

    `.env` being gitignored is not enough on its own: `git add -f` gets past it,
    a stray `.env.local` is a different name, and a key pasted into a .py file
    is not a filename problem at all.

    The hook asks git what is staged, so these tests put a shim named `git` at
    the front of PATH that answers with whatever the case needs. That tests the
    hook's own logic without building a scratch repository, and without any
    real git command running.
    """

    def run_pre_commit(self, names: str, diff: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "git"
            shim.write_text(
                "#!/bin/sh\n"
                "# Answers the three questions the hook asks, and nothing else.\n"
                "# The staged-python query returns nothing: these tests are about\n"
                "# the secret guard, and the ruff stage has its own tests.\n"
                'case "$*" in\n'
                "  *'*.py'*) : ;;\n"
                "  *--name-only*) cat <<'NAMES'\n"
                f"{names}\n"
                "NAMES\n"
                "  ;;\n"
                "  *) cat <<'DIFF'\n"
                f"{diff}\n"
                "DIFF\n"
                "  ;;\n"
                "esac\n"
            )
            shim.chmod(0o755)
            env = dict(os.environ, PATH=f"{tmp}:{os.environ['PATH']}")
            done = subprocess.run(
                [str(PRE_COMMIT)], capture_output=True, text=True, cwd=ROOT, env=env, check=False
            )
            return done.returncode, done.stdout + done.stderr

    def test_a_staged_env_file_is_refused(self):
        for name in (".env", ".env.local", "config/.env"):
            with self.subTest(name=name):
                code, out = self.run_pre_commit(names=name, diff="+BA_GROQ_API_KEY=gsk_x")
                self.assertEqual(code, 1)
                self.assertIn("refusing to commit", out)

    def test_the_example_file_is_still_allowed(self):
        code, out = self.run_pre_commit(names=".env.example", diff="+BA_GROQ_API_KEY=")
        self.assertEqual(code, 0, out)

    def test_a_key_pasted_into_any_file_is_refused(self):
        code, out = self.run_pre_commit(names="core/notes.py", diff='+KEY = "gsk_' + "a" * 52 + '"')
        self.assertEqual(code, 1)
        self.assertIn("Groq API key", out)

    def test_ordinary_content_still_commits(self):
        code, out = self.run_pre_commit(names="notes.md", diff="+nothing secret here")
        self.assertEqual(code, 0, out)
