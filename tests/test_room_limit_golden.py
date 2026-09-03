"""Pin what the room-limit lookup returns, for every sum insured in every policy.

`core/room_limit.py` is the one module in the audit path that reads the
splitter's rendered `[table]` rows as text. That coupling is deliberate - the
whole point of v4 was to take the model out of the room-rent decision, and the
table is where the answer lives - but it means a change to how tables render can
change what the lookup returns without anything failing.

The golden table fixtures pin the *rendering*. This pins the *reading*: the
entitlement itself, per policy and per sum insured. The two together close the
loop, because a rendering change that the table fixtures accept can still move
this file, and this file is the one that decides money.

It exists because the same class of failure has now happened twice. A flattened
table put `5,00,000` beside a limit belonging to the 3L and 4L rows; a merged
cell read by its starting column put a column heading where nine sub-limits
should have been. Neither errored. Both were found by reading output by eye.

Regenerating is a decision, not a formality - read the diff first:

    uv run python tests/test_room_limit_golden.py --update
"""

import difflib
import sys
import unittest
from pathlib import Path

# Running this file directly (--update) puts tests/ on sys.path, not the repo
# root, so core/ is not importable without this.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings
from core.room_limit import RoomEntitlement, lookup, sum_insured_options

FIXTURE = Path(__file__).parent / "fixtures" / "room_limits.txt"
POLICIES = ("star_health", "hdfc_ergo", "niva_bupa")


def describe(entitlement: RoomEntitlement | None) -> str:
    """One line per lookup, carrying the figure and how it was established.

    The clause id is part of the record: a lookup that returns the right rupee
    figure while citing the wrong clause is still wrong, because the citation is
    what the report shows the insured.
    """
    if entitlement is None:
        return "none"
    if entitlement.per_day is not None:
        what = f"per_day={entitlement.per_day:,.0f}"
    elif entitlement.category:
        what = f"category={entitlement.category}"
    elif entitlement.at_actuals:
        what = "at_actuals"
    elif entitlement.defers_to_schedule:
        what = "defers_to_schedule"
    else:
        what = "undecided"
    return f"{what} [{entitlement.clause_id}] decided={entitlement.is_decided()}"


def render() -> str:
    lines: list[str] = []
    for policy in POLICIES:
        options = sum_insured_options(policy)
        lines.append(f"{policy}: {len(options)} sums insured")
        for sum_insured in options:
            lines.append(f"  {sum_insured:>10,}  {describe(lookup(policy, sum_insured))}")
    return "\n".join(lines) + "\n"


def _index_present() -> bool:
    return settings.clauses_path.exists()


@unittest.skipUnless(_index_present(), "data/clauses.json not built")
class RoomLimitGoldenTest(unittest.TestCase):
    def test_every_lookup_is_unchanged(self):
        self.assertTrue(FIXTURE.exists(), f"no fixture at {FIXTURE} - run with --update")
        expected = FIXTURE.read_text(encoding="utf-8")
        actual = render()
        if actual != expected:
            diff = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(),
                    actual.splitlines(),
                    fromfile="fixture",
                    tofile="lookup now",
                    lineterm="",
                )
            )
            self.fail(
                "the room-limit lookup returns something different.\n"
                "If a table rendering changed, this is the accuracy cost of it.\n\n" + diff
            )

    def test_star_health_maps_each_band_to_the_right_entitlement(self):
        """The mapping in words, so the fixture cannot be regenerated into nonsense.

        A golden file records whatever the code did on the day it was written -
        which is exactly how a corrupted II.5 sat in the index while its own
        fixture said it was fine. These assertions state what the PDF says.
        """
        for sum_insured in (100_000, 200_000):
            with self.subTest(sum_insured=sum_insured):
                got = lookup("star_health", sum_insured)
                self.assertEqual(2000.0, got.per_day)
                self.assertEqual("II.1", got.clause_id)
        for sum_insured in (300_000, 400_000):
            with self.subTest(sum_insured=sum_insured):
                got = lookup("star_health", sum_insured)
                self.assertEqual(5000.0, got.per_day)
                self.assertEqual("II.1", got.clause_id)
        for sum_insured in (500_000, 1_000_000, 2_500_000):
            with self.subTest(sum_insured=sum_insured):
                got = lookup("star_health", sum_insured)
                self.assertIsNone(got.per_day, "5L and above grants a category, not a rupee cap")
                self.assertIn("Room", got.category)

    def test_the_other_two_policies_defer_rather_than_invent(self):
        """Neither states a rupee figure, and neither may have one guessed for it."""
        for sum_insured in sum_insured_options("hdfc_ergo"):
            got = lookup("hdfc_ergo", sum_insured)
            self.assertTrue(got.at_actuals, "hdfc_ergo B.1.1 states At Actuals")
            self.assertIsNone(got.per_day)
        for sum_insured in sum_insured_options("niva_bupa"):
            got = lookup("niva_bupa", sum_insured)
            self.assertTrue(got.defers_to_schedule, "niva_bupa 6.2.4 defers to the schedule")
            self.assertFalse(got.is_decided(), "a deferral must not settle the line on its own")

    def test_every_sum_insured_the_form_offers_resolves(self):
        """A dropdown value with no entitlement behind it is a dead end."""
        for policy in POLICIES:
            for sum_insured in sum_insured_options(policy):
                with self.subTest(policy=policy, sum_insured=sum_insured):
                    self.assertIsNotNone(lookup(policy, sum_insured))


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
