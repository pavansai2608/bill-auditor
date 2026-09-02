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
import re
import sys
import unittest
from functools import lru_cache
from pathlib import Path

# Running this file directly (--update) puts tests/ on sys.path, not the repo
# root, so core/ is not importable without this.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pdfplumber

from core.config import settings
from core.splitter import render_table, split_pdf

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

# Every table in every document, not only the eight clauses above. Pinning one
# table and leaving the rest loose is what let star_health II.5 sit in the index
# with a column heading where nine sub-limits should have been - and II.5 was on
# the list. It was the *fixture* that was wrong, frozen from a bad read, because
# a golden file only records what the code did on the day it was written.
#
# The IRDAI list is here too: it is a table, it decides whether a line is paid,
# and it was the one source with no fixture at all.
ALL_PDFS = {**PDFS, "irdai": "non_payable_items.pdf"}

# Tables where a label already sits in a data cell for a *different* reason
# than the II.5 forward-fill, and which are therefore not fixed by that change.
#
# star_health page 15 is the loyalty-bonus illustration. Its column labels come
# from the band above the ruled box, and on that page the band catches the page
# furniture - "STAR HEALTH AND ALLIED INSURAN", "NCE COMPANY LIMITED | P",
# "POLICY WORDINGS" - which is then prefixed to every cell in the row. The
# repeated-header stripping that removes this furniture elsewhere runs at
# document level and the band never sees it. It states no limit and no bill
# line depends on it, so it is recorded rather than chased here; the
# all-tables fixture pins the exact text either way.
KNOWN_LABEL_LEAKS = {"star_health page 15 table 0"}


def _is_data_line(row: str) -> bool:
    """A rendered row whose left-hand cell carries a figure."""
    return bool(re.search(r"\d", row[len("[table] ") :].split(" - ")[0]))


@lru_cache(maxsize=3)
def _clauses(policy: str) -> dict[str, str]:
    """Split straight from the PDF, so this tests the splitter and not the checkpoint."""
    path = settings.policies_dir / PDFS[policy]
    return {c.clause_id: c.text for c in split_pdf(path, policy)}


def fixture_path(policy: str, clause_id: str) -> Path:
    return FIXTURES / f"{policy}__{clause_id}.txt"


def all_tables_path(policy: str) -> Path:
    return FIXTURES / f"all-tables__{policy}.txt"


@lru_cache(maxsize=4)
def _all_tables(policy: str) -> str:
    """Every table the splitter renders, page by page, straight from the PDF.

    Rendered rather than split into clauses on purpose: a table that no clause
    ends up carrying is still a table whose extraction can rot, and this is the
    layer where the rot happens.
    """
    path = settings.policies_dir / ALL_PDFS[policy]
    out: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.find_tables()
            for index, table in enumerate(tables):
                rendered = render_table(page, table, tables)
                if rendered:
                    out.append(f"=== page {page.page_number} table {index} ===")
                    out.append(rendered)
    return "\n".join(out) + "\n"


def _count_tables(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.startswith("=== page "))


def _pdfs_present() -> bool:
    return all((settings.policies_dir / name).exists() for name in ALL_PDFS.values())


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

    def test_every_table_in_every_pdf_is_unchanged(self):
        """The broad net. One clause pinned and the rest loose is what II.5 cost."""
        for policy in sorted(ALL_PDFS):
            with self.subTest(policy=policy):
                path = all_tables_path(policy)
                self.assertTrue(path.exists(), f"no fixture for {policy} - run with --update")
                expected = path.read_text(encoding="utf-8")
                actual = _all_tables(policy)
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
                    self.fail(f"{policy}: table extraction changed\n\n{diff}")

    def test_no_column_heading_is_used_as_a_value(self):
        """The II.5 defect as a rule, so it cannot come back anywhere else.

        A data row that repeats one of its own table's column headings word for
        word is the forward-fill having carried a label down into the data. It
        reads like a limit and is not one.
        """
        for policy in sorted(ALL_PDFS):
            with self.subTest(policy=policy):
                offenders = []
                for block in _all_tables(policy).split("=== page ")[1:]:
                    where = f"{policy} page {block.splitlines()[0].replace(' ===', '')}"
                    rows = [ln for ln in block.splitlines() if ln.startswith("[table]")]
                    headings = set()
                    for row in rows:
                        if not _is_data_line(row):
                            headings.update(
                                cell.strip()
                                for cell in row[len("[table] ") :].split(" - ")
                                if len(cell.strip()) > 25
                            )
                    for row in rows:
                        if not _is_data_line(row):
                            continue
                        for cell in row[len("[table] ") :].split(" - "):
                            if cell.strip() in headings and where not in KNOWN_LABEL_LEAKS:
                                offenders.append(f"{where}: {cell.strip()[:60]}")
                self.assertEqual(
                    [], offenders[:5], f"{len(offenders)} data cells repeat a column heading"
                )

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

    total = 0
    for policy in sorted(ALL_PDFS):
        text = _all_tables(policy)
        count = _count_tables(text)
        total += count
        path = all_tables_path(policy)
        changed = not path.exists() or path.read_text(encoding="utf-8") != text
        path.write_text(text, encoding="utf-8")
        print(f"  {'written' if changed else 'unchanged'}  all tables in {policy}: {count} tables")
    print(f"  {total} tables pinned across {len(ALL_PDFS)} documents")


if __name__ == "__main__":
    if "--update" in sys.argv:
        update()
    else:
        unittest.main()
