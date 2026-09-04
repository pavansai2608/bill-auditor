"""Pin exactly how `eval/derive_key.py` and `eval/answer_key.json` disagree.

The script that first wrote the key no longer reproduces it. Two recorded
decisions were applied to the key on disk and never back-ported: D-12, which
moved 85 citations from the room-rent cap to the definition of associated
medical expenses, and the ruling that B03 and B31 cannot be answered from the
niva_bupa wording at all.

That is a normal thing to happen to an answer key, and it is not a defect. What
would be a defect is nobody knowing. Two failure modes this closes:

* **Silent reversion.** `--write` is refused outright, so the script cannot undo
  a decision by being run. That is asserted here rather than left to a comment.
* **Silent drift.** Any *new* disagreement - a change to `derive_key.py`, a
  change to the key, a bill edited - changes the golden file below and fails.
  Someone then has to look at the diff and say which side is right.

The golden file is the honest artefact here. It says, line by line, where the
first derivation and the current key differ, so "the key has moved on" is a
readable list rather than a claim.

Regenerating is a decision, not a formality - read the diff first:

    uv run python tests/test_derive_key_divergence.py --update
"""

import difflib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURE = Path(__file__).parent / "fixtures" / "derive_key_divergence.txt"
KEY_PATH = ROOT / "eval" / "answer_key.json"
BILLS_DIR = ROOT / "eval" / "bills"
SCRIPT = ROOT / "eval" / "derive_key.py"


def derive_key_module():
    """Load the script without going through eval/ as a package."""
    sys.path.insert(0, str(ROOT / "eval"))
    spec = importlib.util.spec_from_file_location("derive_key_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render() -> str:
    """Every line where the first derivation and the current key disagree."""
    module = derive_key_module()
    key = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    entries = module.load_non_payable()

    rows: list[str] = []
    same = 0
    for path in sorted(BILLS_DIR.glob("B*.json")):
        bill_id = path.stem
        bill = json.loads(path.read_text(encoding="utf-8"))
        fresh = module.derive_bill(bill, entries)
        for index, (now, first) in enumerate(
            zip(key["bills"][bill_id]["lines"], fresh, strict=True)
        ):
            differences = []
            if now.get("clause_id") != first.get("clause_id"):
                differences.append(f"clause {first.get('clause_id')} -> {now.get('clause_id')}")
            if now.get("allowed") != first.get("allowed"):
                differences.append(f"allowed {first.get('allowed')} -> {now.get('allowed')}")
            if bool(now.get("needs_human")) != bool(first.get("needs_human")):
                differences.append(
                    f"needs_human {bool(first.get('needs_human'))} -> {bool(now.get('needs_human'))}"
                )
            if differences:
                rows.append(
                    f"{bill_id} line {index + 1:2d}  {now['item'][:44]:46s} "
                    + "; ".join(differences)
                )
            else:
                same += 1

    header = [
        "# Where eval/derive_key.py and eval/answer_key.json disagree.",
        "# Regenerate with: uv run python tests/test_derive_key_divergence.py --update",
        f"# lines that still agree: {same}",
        f"# lines that disagree:    {len(rows)}",
        "",
    ]
    return "\n".join(header + rows) + "\n"


class DeriveKeyCannotRevertADecisionTest(unittest.TestCase):
    def test_write_is_refused(self):
        """The whole point. Running it with --write must change nothing."""
        before = KEY_PATH.read_bytes()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--write"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertNotEqual(0, result.returncode, "--write exited 0; it must refuse")
        self.assertIn("refused", (result.stderr + result.stdout).lower())
        self.assertEqual(before, KEY_PATH.read_bytes(), "--write modified the answer key")

    def test_a_dry_run_still_works(self):
        """It is still the record of where the key came from; reading it must not error."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=ROOT
        )
        self.assertEqual(0, result.returncode, result.stderr)


class TheDivergenceIsRecordedTest(unittest.TestCase):
    def test_it_is_exactly_what_the_golden_file_says(self):
        self.assertTrue(FIXTURE.exists(), f"no fixture at {FIXTURE} - run with --update")
        expected = FIXTURE.read_text(encoding="utf-8")
        actual = render()
        if actual != expected:
            diff = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(),
                    actual.splitlines(),
                    fromfile="recorded divergence",
                    tofile="divergence now",
                    lineterm="",
                )
            )
            self.fail(
                "derive_key.py and answer_key.json disagree differently than recorded.\n"
                "One of the two moved. Decide which is right before regenerating.\n\n" + diff
            )

    def test_the_two_have_not_silently_converged(self):
        """A zero-divergence fixture would mean the key had been regenerated.

        That is the thing the guard exists to prevent, so it is asserted rather
        than assumed: if this ever passes with an empty list, someone ran the
        script over the key and 87 decisions went with it.
        """
        rows = [
            line
            for line in FIXTURE.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        self.assertGreater(len(rows), 0, "the key appears to have been regenerated from the script")


def update() -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    text = render()
    changed = not FIXTURE.exists() or FIXTURE.read_text(encoding="utf-8") != text
    FIXTURE.write_text(text, encoding="utf-8")
    print(f"{'written' if changed else 'unchanged'}  {FIXTURE}")
    print(text)


if __name__ == "__main__":
    if "--update" in sys.argv:
        update()
    else:
        unittest.main()
