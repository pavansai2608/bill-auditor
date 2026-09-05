"""The floor under the clause index: no splitter change may lose a page.

**Why this exists.** A one-line change to `_region_text` - deleting the escape
hatch that lets a clause heading survive inside a table region - removed the
flattened rubbish from `hdfc_ergo E.2.1` and, in the same stroke, deleted pages
50 and 51 of that document from the index: 6,314 characters, the 16-row
plan-comparison grid, and the legend that defines what "Not Covered" means in
it. **All 462 unit tests passed. All 6 golden table tests passed.** Nothing in
the suite could see content leaving the index, because every test asked whether
what was there was correct and none asked whether it was still there.

So this file asks the other question, per policy:

- does the index still hold as many characters as it did?
- is every source page that reaches the index today still reaching it?

Both are **floors, not equalities**. Growth passes. A splitter change that drops
a page turns this red whatever else it improves, and that is the point.

`tests/fixtures/index_coverage.json` holds the pinned numbers. There is
deliberately **no `--update` flag**. Raising the floor is a decision made by
editing that file by hand, with the diff read first - lowering it, more so.

Page coverage is measured by content, not by `Clause.page`. For every page, the
longest lines are squashed to bare alphanumerics and looked for in the squashed
index. Squashing is what makes it survive `join_wrapped_lines`, which glues a
clause's lines together and would defeat an exact match. A page counts as
covered when any one of its probes is found, so a clause legitimately merging
into one that starts on an earlier page still passes - what fails is content
that is nowhere at all.

Fifteen pages are uncovered today and are not in the fixture: contents pages,
address blocks, and annexure grids whose headings `is_table_debris` rejects.
The fixture records what is covered now. It does not claim that is everything.
"""

import json
import re
import unittest
from functools import cache
from pathlib import Path

from core.config import settings
from core.splitter import clean_pages, extract_pages, split_pdf

FIXTURE = Path(__file__).parent / "fixtures" / "index_coverage.json"

PDFS = {
    "star_health": "star_health.pdf",
    "hdfc_ergo": "hdfc_ergo.pdf",
    "niva_bupa": "niva_bupa.pdf",
}

# A probe must be long enough that finding it is not a coincidence.
MIN_PROBE_CHARS = 30


def _squash(text: str) -> str:
    """Bare alphanumerics, so line joining and spacing cannot break a match."""
    return re.sub(r"[^0-9a-z]", "", text.lower())


@cache
def _index(policy: str) -> tuple[int, int, str]:
    """Characters, clause count and the squashed text of one policy's index."""
    clauses = split_pdf(settings.policies_dir / PDFS[policy], policy)
    characters = sum(len(clause.text) for clause in clauses)
    return characters, len(clauses), _squash(" ".join(clause.text for clause in clauses))


@cache
def _covered_pages(policy: str) -> frozenset[int]:
    """Pages of the PDF whose text can still be found in the index."""
    _, _, blob = _index(policy)
    covered = set()
    for page in clean_pages(extract_pages(settings.policies_dir / PDFS[policy])):
        probes = [_squash(line) for line in page.text.split("\n")]
        probes = [probe for probe in probes if len(probe) >= MIN_PROBE_CHARS]
        if any(probe[:MIN_PROBE_CHARS] in blob for probe in probes):
            covered.add(page.page)
    return frozenset(covered)


class IndexCoverageTest(unittest.TestCase):
    """Nothing may leave the index unnoticed."""

    floor = json.loads(FIXTURE.read_text())

    def test_no_policy_loses_indexed_text(self):
        """Character count is a floor. Text that disappears has to be argued for."""
        for policy in sorted(PDFS):
            with self.subTest(policy=policy):
                characters, _, _ = _index(policy)
                pinned = self.floor[policy]["characters"]
                self.assertGreaterEqual(
                    characters,
                    pinned,
                    f"{policy}: the index shrank from {pinned} to {characters} characters "
                    f"({pinned - characters} lost). Find where that text went before "
                    f"editing {FIXTURE.name}.",
                )

    def test_no_source_page_leaves_the_index(self):
        """Every page reaching the index today must still reach it."""
        for policy in sorted(PDFS):
            with self.subTest(policy=policy):
                covered = _covered_pages(policy)
                pinned = set(self.floor[policy]["pages"])
                lost = sorted(pinned - covered)
                self.assertEqual(
                    lost,
                    [],
                    f"{policy}: page(s) {lost} no longer appear anywhere in the index. "
                    f"A page can only stop being covered because its content was "
                    f"dropped, not because a clause moved.",
                )

    def test_no_policy_loses_clauses_wholesale(self):
        """A few clauses may go; a tenth of them going is a different event."""
        for policy in sorted(PDFS):
            with self.subTest(policy=policy):
                _, clauses, _ = _index(policy)
                pinned = self.floor[policy]["clauses"]
                self.assertGreaterEqual(
                    clauses,
                    int(pinned * 0.95),
                    f"{policy}: {pinned} clauses became {clauses}. More than 5% of the "
                    f"index is gone.",
                )


if __name__ == "__main__":
    unittest.main()
