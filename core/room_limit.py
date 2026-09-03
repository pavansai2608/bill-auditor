"""The room rent entitlement, read from the policy rather than asked for.

Room rent is a lookup, not a judgement: the policy, the sum insured and the
table row settle it. Asking an 8B model to read a nine-row table and report the
figure for one sum insured is a question it can get wrong quietly - on B05 it
returned 800/day where the table grants a room category and the charge was
4,000/day, inventing a breach that then rescaled three other lines through the
second pass. One misread figure was worth four wrong lines.

So the model is not asked. `lookup()` reads the `[table]` rows the splitter
already extracts, matches the sum insured, and returns one of four answers:

* a rupee **per-day cap** (star_health up to 4,00,000)
* a **room category** with no rupee figure (star_health from 5,00,000 up)
* **at actuals** - the wording states a default and no figure (hdfc_ergo B.1.1)
* **defers to schedule** - the wording hands the figure to the policy schedule
  and states no fallback (niva_bupa 6.2.4)

Only when no row and no wording match does it return `None`, and the judge is
asked as before - marked in the trace, so a silent fallback cannot be mistaken
for a lookup.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from core.ingest import load_clauses
from core.logging_conf import get_logger
from core.models import Clause, PolicySchedule

log = get_logger(__name__)

# One extracted table row: "[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.)
# Up to 5,000/- per day". The row is trusted because the extraction is frozen
# by tests/fixtures/tables/ and any drift fails the golden test.
# The row must *start* with the Sum Insured column. Matching "Sum Insured"
# anywhere caught hdfc_ergo E.1.4, a plan-comparison table whose every row
# mentions the Base Sum Insured, and read a room limit out of an AYUSH row.
TABLE_ROW_RE = re.compile(
    r"^\[table\]\s*Sum\s+Insured\b[^\d]*([\d,]+)[^\n]*?Limit[^)\n]*\)?\s*[-:]?\s*(.+)$",
    re.I | re.M,
)
RUPEE_LIMIT_RE = re.compile(r"(?:up\s*to\s*)?(?:rs\.?\s*)?([\d,]+)\s*/?-?\s*per\s*day", re.I)
CATEGORY_LIMIT_RE = re.compile(r"([A-Za-z][A-Za-z/ .]*room)", re.I)

# Wording that decides the question without a table.
# The PDF uses a curly quote around 'At Actuals'; match either kind.
AT_ACTUALS_RE = re.compile("room rent limit shall be\\s*[\u2018\u2019'\"]?at actuals", re.I)
DEFERS_RE = re.compile(
    r"(?:eligible\s+)?room\s+(?:rent|category)[^.]{0,80}"
    r"(?:as\s+)?specified\s+in\s+(?:the\s+|your\s+)?policy\s+schedule",
    re.I,
)
ROOM_CLAUSE_RE = re.compile(r"room rent|room, boarding|room,boarding|room category", re.I)

# Ascending, so an occupied room can be compared with an entitlement stated as
# a category. A shared room cannot exceed any entitlement; a suite exceeds all
# but itself.
ROOM_CATEGORIES: list[tuple[re.Pattern, int]] = [
    (re.compile(r"shared|sharing|general ward|twin", re.I), 1),
    (re.compile(r"single standard a/?c|standard single|single a/?c", re.I), 2),
    (re.compile(r"single private|private room", re.I), 3),
    (re.compile(r"deluxe", re.I), 4),
    (re.compile(r"suite", re.I), 5),
]


def room_rank(text: str) -> int | None:
    """Where a room sits in the ladder, or None if the wording does not say."""
    for pattern, rank in ROOM_CATEGORIES:
        if pattern.search(text):
            return rank
    return None


@dataclass(frozen=True)
class RoomEntitlement:
    """What the policy grants for a room, and how that was established."""

    clause_id: str | None
    source: str
    per_day: float | None = None
    category: str | None = None
    at_actuals: bool = False
    defers_to_schedule: bool = False

    def is_decided(self) -> bool:
        """Does this settle the room line without asking anyone anything?"""
        return self.per_day is not None or self.at_actuals or self.category is not None


@lru_cache(maxsize=8)
def _room_clauses(policy: str) -> tuple[Clause, ...]:
    """Clauses that speak about the room entitlement, longest text first.

    Longest first because the clause carrying the table is the substantive one;
    a passing mention of "room rent" in a definition is not what decides this.
    """
    matches = [
        clause
        for clause in load_clauses()
        if clause.policy == policy and ROOM_CLAUSE_RE.search(clause.text)
    ]
    return tuple(sorted(matches, key=lambda c: len(c.text), reverse=True))


def _rows(clause: Clause) -> dict[int, str]:
    """The sum-insured rows of this clause's room table, as {rupees: limit}.

    A row counts only if its limit column reads as a room entitlement - a
    per-day rupee figure or a room category. Anything else is a different
    table that happens to be keyed on sum insured.
    """
    found: dict[int, str] = {}
    for amount, limit in TABLE_ROW_RE.findall(clause.text):
        text = limit.strip()
        if not (RUPEE_LIMIT_RE.search(text) or CATEGORY_LIMIT_RE.search(text)):
            continue
        try:
            key = int(amount.replace(",", ""))
        except ValueError:
            continue
        found.setdefault(key, text)
    return found


def governs_room_rent(clause: Clause) -> bool:
    """Is this the clause the room entitlement is actually stated in?

    Decided from the clause's own content and never from the bill line: it
    either carries the sum-insured rows the entitlement is read out of, or its
    wording states the limit ("At Actuals") or hands it to the policy schedule.

    `ROOM_CLAUSE_RE` is deliberately not the test. It matches any clause that
    says "room rent" in passing - a definition, an exclusion, a benefit that
    mentions the room while capping something else - and treating those as the
    source of a room cap would reject verdicts that have nothing to do with the
    room. The three things checked here are the same three `lookup()` reads.
    """
    return bool(_rows(clause)) or bool(
        AT_ACTUALS_RE.search(clause.text) or DEFERS_RE.search(clause.text)
    )


def primary_room_clause(policy: str) -> Clause | None:
    """The clause a room-rent verdict should cite for this policy.

    The one that carries the table, else the one that states the limit in
    words, else the longest. Without this the schedule path cited whichever
    clause happened to be longest - `E.1.4` for hdfc_ergo, which mentions room
    rent but does not grant it.
    """
    clauses = _room_clauses(policy)
    for clause in clauses:
        if _rows(clause):
            return clause
    for clause in clauses:
        if AT_ACTUALS_RE.search(clause.text) or DEFERS_RE.search(clause.text):
            return clause
    return clauses[0] if clauses else None


def table_lookup(policy: str, sum_insured: float) -> RoomEntitlement | None:
    """The table row for this sum insured, if one matches exactly.

    Exact match only. Interpolating between rows would be inventing a figure
    the policy does not state, which is the whole failure this replaces.
    """
    for clause in _room_clauses(policy):
        rows = _rows(clause)
        if not rows:
            continue
        limit_text = rows.get(int(sum_insured))
        if limit_text is None:
            log.info(
                "no %s table row for sum insured %s (rows: %s)",
                policy,
                f"{int(sum_insured):,}",
                ", ".join(f"{k:,}" for k in sorted(rows)),
            )
            continue

        rupees = RUPEE_LIMIT_RE.search(limit_text)
        if rupees:
            per_day = float(rupees.group(1).replace(",", ""))
            return RoomEntitlement(
                clause_id=clause.clause_id,
                source=(
                    f"{clause.clause_id} table: Sum Insured {int(sum_insured):,} -> {limit_text}"
                ),
                per_day=per_day,
            )

        category = CATEGORY_LIMIT_RE.search(limit_text)
        if category:
            return RoomEntitlement(
                clause_id=clause.clause_id,
                source=(
                    f"{clause.clause_id} table: Sum Insured {int(sum_insured):,} "
                    f'-> "{limit_text}" - a room category, no rupee limit stated'
                ),
                category=category.group(1).strip(),
            )
    return None


# The sums insured the built-in policies are sold at. Used only when a policy
# states no room table of its own - hdfc_ergo and niva_bupa put the room
# entitlement on the schedule instead, so their tables cannot supply this.
STANDARD_SUM_INSURED = [300000, 500000, 1000000, 2500000]


def sum_insured_options(policy: str) -> list[int]:
    """The sums insured this policy actually supports, for the dropdown.

    star_health prices its room limit by sum insured, so its own table is the
    list. The other two do not, so they fall back to the standard set rather
    than to a number invented per policy.
    """
    for clause in _room_clauses(policy):
        rows = _rows(clause)
        if rows:
            return sorted(rows)
    return list(STANDARD_SUM_INSURED)


def wording_lookup(policy: str) -> RoomEntitlement | None:
    """What the wording says when there is no table to read."""
    for clause in _room_clauses(policy):
        if AT_ACTUALS_RE.search(clause.text):
            return RoomEntitlement(
                clause_id=clause.clause_id,
                source=(
                    f"{clause.clause_id}: room rent limit is 'At Actuals' unless the "
                    "policy schedule says otherwise, and none was given"
                ),
                at_actuals=True,
            )
    for clause in _room_clauses(policy):
        if DEFERS_RE.search(clause.text):
            return RoomEntitlement(
                clause_id=clause.clause_id,
                source=(
                    f"{clause.clause_id}: the room entitlement is set by the policy "
                    "schedule and the wording states no fallback"
                ),
                defers_to_schedule=True,
            )
    return None


def lookup(
    policy: str, sum_insured: float, schedule: PolicySchedule | None = None
) -> RoomEntitlement | None:
    """The room entitlement for this policy and sum insured. No model call.

    The insured's own schedule wins where it is given: it is the document the
    wording defers to, so a figure on it is not an assumption.
    """
    if schedule is not None and schedule.room_limit_per_day is not None:
        clause = primary_room_clause(policy)
        return RoomEntitlement(
            clause_id=clause.clause_id if clause else None,
            source=(
                f"policy schedule states a room limit of Rs {schedule.room_limit_per_day:,.0f} "
                "per day"
            ),
            per_day=float(schedule.room_limit_per_day),
        )
    if schedule is not None and schedule.room_category:
        clause = primary_room_clause(policy)
        return RoomEntitlement(
            clause_id=clause.clause_id if clause else None,
            source=f"policy schedule states a room category of {schedule.room_category}",
            category=schedule.room_category,
        )

    return table_lookup(policy, sum_insured) or wording_lookup(policy)
