"""Golden-file tests for table extraction.

The table code has broken three times, and each break was silent: the text
still looked like text, so nothing failed. Once a row read
"Sum Insured 5,00,000 - Up to 5,000/- per day" when that limit belongs to the
3L and 4L rows, and the only way to notice was to read the output by eye.

So the exact extracted text of the clauses that decide money is frozen here.
Any change to the splitter that alters one of them fails this test and prints
the diff. If the change is intended, regenerate the fixtures deliberately:

    uv run python tests/test_tables_golden.py --update

Regenerating is a decision, not a formality. Read the diff first.
"""

import difflib
import sys
import unittest
from functools import lru_cache
from pathlib import Path

# Running this file directly (--update) puts tests/ on sys.path, not the repo
# root, so core/ is not importable without this.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings
from core.splitter import split_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "tables"

# The clauses a wrong reading would turn into a wrong payout.
GOLDEN = [
    (
        "star_health",
        "II.1",
        "room rent table - the per-day limit for 3L/4L and the category from 5L up",
    ),
    ("star_health", "II.5", "modern treatments - six-column sub-limit grid"),
    ("star_health", "II.20", "shared accommodation - a benefit, not a room rent cap"),
    ("star_health", "II.8", "road ambulance - two limits with different units in one sentence"),
    ("hdfc_ergo", "B.1.1", "room rent 'At Actuals unless the Policy Schedule says otherwise'"),
    ("hdfc_ergo", "B.1.1.1", "proportionate deduction - what the second pass is built on"),
    ("hdfc_ergo", "E.1.6", "plan-variant comparison grid"),
    ("niva_bupa", "6.2.4", "pro-rata formula for a higher room category"),
]

PDFS = {
    "star_health": "star_health.pdf",
    "hdfc_ergo": "hdfc_ergo.pdf",
    "niva_bupa": "niva_bupa.pdf",
}


@lru_cache(maxsize=3)
def _clauses(policy: str) -> dict[str, str]:
    """Split straight from the PDF, so this tests the splitter and not the checkpoint."""
    path = settings.policies_dir / PDFS[policy]
    return {c.clause_id: c.text for c in split_pdf(path, policy)}


def fixture_path(policy: str, clause_id: str) -> Path:
    return FIXTURES / f"{policy}__{clause_id}.txt"


def _pdfs_present() -> bool:
    return all((settings.policies_dir / name).exists() for name in PDFS.values())


@unittest.skipUnless(_pdfs_present(), "policy PDFs not present")
class TableGoldenTest(unittest.TestCase):
    def test_extracted_text_is_unchanged(self):
        for policy, clause_id, why in GOLDEN:
            with self.subTest(policy=policy, clause=clause_id):
                path = fixture_path(policy, clause_id)
                self.assertTrue(
                    path.exists(),
                    f"no fixture for {policy}:{clause_id} - run with --update",
                )
                expected = path.read_text(encoding="utf-8")
                actual = _clauses(policy).get(clause_id)
                self.assertIsNotNone(
                    actual, f"{policy}:{clause_id} is no longer produced by the splitter"
                )
                if actual != expected:
                    diff = "\n".join(
                        difflib.unified_diff(
                            expected.splitlines(),
                            actual.splitlines(),
                            fromfile="fixture",
                            tofile="extracted now",
                            lineterm="",
                        )
                    )
                    self.fail(f"{policy}:{clause_id} changed ({why})\n\n{diff}")

    def test_room_rent_rows_map_to_the_right_sum_insured(self):
        """The specific misreading that started all this.

        Flattened, the table put 5,00,000 next to the Rs 5,000/day limit that
        belongs to 3L and 4L. A bill at 5L would have been capped at a limit
        the policy does not give it.
        """
        text = _clauses("star_health")["II.1"]
        rows = [ln for ln in text.split("\n") if ln.startswith("[table]")]
        by_si = {}
        for row in rows:
            for si in ("1,00,000", "2,00,000", "3,00,000", "4,00,000", "5,00,000", "25,00,000"):
                if f"Sum Insured (Rs.) {si}/-" in row:
                    by_si[si] = row
        self.assertEqual(len(by_si), 6, "not every sum insured row was rendered")

        for si in ("1,00,000", "2,00,000"):
            self.assertIn("2,000/- per day", by_si[si], si)
        for si in ("3,00,000", "4,00,000"):
            self.assertIn("5,000/- per day", by_si[si], si)
        for si in ("5,00,000", "25,00,000"):
            self.assertIn("Single Standard A/C Room", by_si[si], si)
            self.assertNotIn("per day", by_si[si], f"{si} must give a category, not a rupee cap")

    def test_ambulance_states_both_of_its_limits(self):
        text = _clauses("star_health")["II.8"]
        self.assertIn("750", text)
        self.assertIn("1,500", text)
        self.assertIn("per hospitalization", text)
        self.assertIn("Policy Period", text)

    def test_no_fixture_is_empty(self):
        for policy, clause_id, _ in GOLDEN:
            with self.subTest(clause=clause_id):
                self.assertGreater(len(fixture_path(policy, clause_id).read_text()), 80)


def update() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for policy, clause_id, why in GOLDEN:
        text = _clauses(policy).get(clause_id)
        if text is None:
            print(f"  MISSING  {policy}:{clause_id} - splitter no longer produces it")
            continue
        path = fixture_path(policy, clause_id)
        changed = not path.exists() or path.read_text(encoding="utf-8") != text
        path.write_text(text, encoding="utf-8")
        print(f"  {'written' if changed else 'unchanged'}  {policy}:{clause_id}  ({why})")


if __name__ == "__main__":
    if "--update" in sys.argv:
        update()
    else:
        unittest.main()
