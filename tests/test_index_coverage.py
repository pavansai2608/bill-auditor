"""The floor under the clause index: no change may lose a page.

**Why this exists.** A one-line change to `_region_text` - deleting the escape
hatch that lets a clause heading survive inside a table region - removed the
flattened rubbish from `hdfc_ergo E.2.1` and, in the same stroke, deleted pages
50 and 51 of that document from the index: 6,314 characters, the 16-row
plan-comparison grid, and the legend defining what "Not Covered" means in it.
**All 462 unit tests passed. All 6 golden table tests passed.** Nothing in the
suite could see content leaving the index, because every test asked whether
what was there was correct and none asked whether it was still there.

So this file asks the other question, per policy:

- does the index still hold as many characters as it did?
- is every source page that reaches the index still reaching it?

Both are **floors, not equalities**. Growth passes. A change that drops a page
turns this red whatever else it improves, and that is the point.

**It reads `data/clauses.json`, not the PDFs.** It used to re-split the
documents, which made it nine errors out of nine in Jenkins and green here:
`data/policies/*.pdf` is gitignored, so a checkout has no PDFs and
`pdfplumber.open` raised `FileNotFoundError` before any assertion ran. A guard
that only runs on the author's machine is not a guard, and this one exists
precisely because 474 tests passed while two pages left the index.

The committed checkpoint is also the honest target: it is what the eval, the
API and the containers actually read. The cost is that a splitter change which
has not been re-ingested is invisible here - fairly, since it is invisible to
everything else too - and extraction fidelity is `tests/test_tables_golden.py`,
which does read the PDFs and skips without them.

Page coverage is measured by content, not by `Clause.page`. Each page is pinned
in the fixture as a 30-character probe: a line of that page squashed to bare
alphanumerics, chosen because it could be found in the index when the floor was
measured. Squashing is what survives `join_wrapped_lines`, which glues a
clause's lines together and would defeat an exact match. A clause legitimately
merging into one that starts on an earlier page still passes; what fails is
content that is nowhere at all.

Fifteen pages are not pinned: contents pages, address blocks, and annexure
grids whose headings `is_table_debris` rejects. The fixture records what was
covered. It does not claim that is everything.

`tests/fixtures/index_coverage.json` holds the pinned numbers. There is
deliberately **no `--update` flag**. Raising the floor is a decision made by
editing that file by hand, with the diff read first - lowering it, more so.
"""

import json
import re
import unittest
from functools import cache
from pathlib import Path

from core.config import settings

FIXTURE = Path(__file__).parent / "fixtures" / "index_coverage.json"

# A probe must be long enough that finding it is not a coincidence.
PROBE_CHARS = 30


def _squash(text: str) -> str:
    """Bare alphanumerics, so line joining and spacing cannot break a match."""
    return re.sub(r"[^0-9a-z]", "", text.lower())


@cache
def _index(policy: str) -> tuple[int, int, str]:
    """Characters, clause count and the squashed text of one policy's index."""
    clauses = [
        clause
        for clause in json.loads(settings.clauses_path.read_text())
        if clause["policy"] == policy
    ]
    characters = sum(len(clause["text"]) for clause in clauses)
    return characters, len(clauses), _squash(" ".join(c["text"] for c in clauses))


class IndexCoverageTest(unittest.TestCase):
    """Nothing may leave the index unnoticed."""

    floor = json.loads(FIXTURE.read_text())
    policies = sorted(key for key in floor if not key.startswith("_"))

    @classmethod
    def setUpClass(cls):
        if not settings.clauses_path.exists():
            raise AssertionError(
                f"{settings.clauses_path} is missing. It is a committed checkpoint, "
                f"not a build artefact - a checkout has it. Do not make this test skip."
            )

    def test_no_policy_loses_indexed_text(self):
        """Character count is a floor. Text that disappears has to be argued for."""
        for policy in self.policies:
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
        """Every page reaching the index when this was pinned must still reach it."""
        for policy in self.policies:
            with self.subTest(policy=policy):
                _, _, blob = _index(policy)
                lost = sorted(
                    (
                        int(page)
                        for page, probe in self.floor[policy]["pages"].items()
                        if probe not in blob
                    ),
                )
                self.assertEqual(
                    lost,
                    [],
                    f"{policy}: page(s) {lost} no longer appear anywhere in the index. "
                    f"A page can only stop being covered because its content was "
                    f"dropped, not because a clause moved.",
                )

    def test_no_policy_loses_clauses_wholesale(self):
        """A few clauses may go; a tenth of them going is a different event."""
        for policy in self.policies:
            with self.subTest(policy=policy):
                _, clauses, _ = _index(policy)
                pinned = self.floor[policy]["clauses"]
                self.assertGreaterEqual(
                    clauses,
                    int(pinned * 0.95),
                    f"{policy}: {pinned} clauses became {clauses}. More than 5% of the "
                    f"index is gone.",
                )

    def test_every_probe_is_long_enough_to_mean_something(self):
        """A short probe would match by accident and the guard would go quiet."""
        for policy in self.policies:
            for page, probe in self.floor[policy]["pages"].items():
                with self.subTest(policy=policy, page=page):
                    self.assertEqual(PROBE_CHARS, len(probe))
                    self.assertRegex(probe, r"^[0-9a-z]+$")


if __name__ == "__main__":
    unittest.main()
