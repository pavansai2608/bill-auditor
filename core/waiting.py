"""Waiting periods: a date comparison, not a judgement.

Whether a claim falls inside a waiting period is arithmetic on two dates and a
number the clause states. Nothing about it needs a model, and asking one
invites the failure seen on B03, where the judge applied Niva Bupa's 24-month
specified-disease exclusion to a cataract admitted **62 months** after the
policy began and zeroed a line the policy pays in full. It was confident, it
cited a real clause, and it was wrong by five years.

Three periods, identified by their IRDAI exclusion codes rather than by clause
number, because all three policies carry the codes and the numbering differs:

* **Excl01** - pre-existing disease, 36 months. Never applied here: nothing on
  a hospital bill says whether a condition pre-existed the policy, and
  assuming it would zero a bill on a fact no input carries. Recorded, not used.
* **Excl02** - specified diseases and procedures, 24 months.
* **Excl03** - any illness within 30 days of the first policy start, except an
  accident.

The specified-disease rule fires only when the condition named on the bill is
**confirmed in that policy's own clause text**. hdfc_ergo and niva_bupa list
their conditions; star_health's III.2 ends with "f. List of specific
diseases/procedures;" and the list itself is not in the extracted text, so for
star_health this abstains from the rule rather than zeroing a bill against a
list it cannot read. See KNOWN_LIMITATIONS.md.
"""

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from core.ingest import load_clauses
from core.logging_conf import get_logger
from core.models import Clause

log = get_logger(__name__)

PED_CODE_RE = re.compile(r"excl\s?0*1\b", re.I)
SPECIFIED_CODE_RE = re.compile(r"excl\s?0*2\b", re.I)
INITIAL_CODE_RE = re.compile(r"excl\s?0*3\b", re.I)

MONTHS_RE = re.compile(r"expiry of\s*(\d+)\s*months", re.I)
DAYS_RE = re.compile(r"within\s*(\d+)\s*days", re.I)

# The IRDAI-standard 24-month list, as the three policies word it. A term is
# only acted on once it has been found in the policy's own clause text.
CONDITIONS_RE = re.compile(
    r"cataract|hernia|knee replacement|joint replacement|hysterectomy|piles|"
    r"fistula|fissure|sinusitis|tonsil|adenoid|varicose|gall\s?bladder|"
    r"cholecyst|calculi|kidney stone|prostat|hydrocele",
    re.I,
)

# Every one of the three carves out accidents from the 30-day rule.
ACCIDENT_RE = re.compile(r"accident|injury|trauma|fracture|road traffic|\brta\b|burn", re.I)


def months_between(start: date, end: date) -> int:
    """Whole months served, counting a part-month as not yet served."""
    return (
        (end.year - start.year) * 12 + (end.month - start.month) - (1 if end.day < start.day else 0)
    )


def days_between(start: date, end: date) -> int:
    return (end - start).days


def _parse(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        log.warning("could not read a date from %r", value)
        return None


@dataclass(frozen=True)
class WaitingPeriod:
    """One waiting period as a policy states it."""

    kind: str  # "ped" | "specified" | "initial"
    clause_id: str
    months: int | None = None
    days: int | None = None


@dataclass(frozen=True)
class WaitingVerdict:
    """The bill-level answer: excluded, or not, and why."""

    excluded: bool
    clause_id: str | None = None
    reason: str = ""
    kind: str | None = None
    note: str = ""


@lru_cache(maxsize=8)
def periods(policy: str) -> tuple[WaitingPeriod, ...]:
    """The waiting periods this policy states, found by exclusion code.

    One clause can carry all three - hdfc_ergo C.1 does - so each code is
    looked for independently and may resolve to the same clause id.
    """
    clauses = [c for c in load_clauses() if c.policy == policy]
    found: list[WaitingPeriod] = []

    for kind, code in (
        ("ped", PED_CODE_RE),
        ("specified", SPECIFIED_CODE_RE),
        ("initial", INITIAL_CODE_RE),
    ):
        for clause in sorted(clauses, key=lambda c: len(c.text)):
            if not code.search(clause.text):
                continue
            if kind == "initial":
                days = DAYS_RE.search(clause.text)
                if days:
                    found.append(
                        WaitingPeriod(
                            kind=kind, clause_id=clause.clause_id, days=int(days.group(1))
                        )
                    )
                    break
            else:
                months = MONTHS_RE.findall(clause.text)
                if months:
                    # A clause carrying several codes states several periods;
                    # 36 belongs to Excl01 and 24 to Excl02.
                    want = "36" if kind == "ped" else "24"
                    value = want if want in months else months[0]
                    found.append(
                        WaitingPeriod(kind=kind, clause_id=clause.clause_id, months=int(value))
                    )
                    break
    return tuple(found)


def _period(policy: str, kind: str) -> WaitingPeriod | None:
    return next((p for p in periods(policy) if p.kind == kind), None)


@lru_cache(maxsize=8)
def _waiting_clause_ids(policy: str) -> frozenset[str]:
    return frozenset(p.clause_id for p in periods(policy))


def is_waiting_clause(policy: str, clause_id: str | None) -> bool:
    """Does this clause id state a waiting period for this policy?"""
    return clause_id is not None and clause_id in _waiting_clause_ids(policy)


def _clause(policy: str, clause_id: str) -> Clause | None:
    return next(
        (c for c in load_clauses() if c.policy == policy and c.clause_id == clause_id), None
    )


def confirmed_condition(policy: str, items: list[str]) -> tuple[str | None, WaitingPeriod | None]:
    """A listed condition named on the bill *and* in the policy's own clause.

    Both halves are required. The condition list is what makes the exclusion
    apply, so acting on a term the document does not carry would be zeroing a
    bill against a list this system cannot read.
    """
    period = _period(policy, "specified")
    if period is None:
        return None, None
    clause = _clause(policy, period.clause_id)
    if clause is None:
        return None, None

    for item in items:
        match = CONDITIONS_RE.search(item)
        if match and re.search(re.escape(match.group(0)), clause.text, re.I):
            return match.group(0), period
    return None, period


def assess(
    items: list[str],
    policy: str,
    policy_start_date: str | date | None,
    admission_date: str | date | None,
) -> WaitingVerdict:
    """Is this whole admission inside a waiting period? Dates only, no model."""
    start, admitted = _parse(policy_start_date), _parse(admission_date)
    if start is None or admitted is None:
        return WaitingVerdict(
            excluded=False,
            note="no policy start or admission date was given, so waiting periods were not assessed",
        )

    if ACCIDENT_RE.search(" | ".join(items)):
        return WaitingVerdict(
            excluded=False,
            note="the bill reads as an accident, which every waiting period carves out",
        )

    served_months = months_between(start, admitted)
    served_days = days_between(start, admitted)

    condition, specified = confirmed_condition(policy, items)
    if condition and specified and served_months < (specified.months or 0):
        return WaitingVerdict(
            excluded=True,
            clause_id=specified.clause_id,
            kind="specified",
            reason=(
                f"{specified.clause_id}: {condition} is on the {specified.months}-month "
                f"specified-disease list and the policy had run "
                f"{served_months} months at admission, so nothing is payable"
            ),
        )

    initial = _period(policy, "initial")
    if initial and initial.days and served_days < initial.days:
        return WaitingVerdict(
            excluded=True,
            clause_id=initial.clause_id,
            kind="initial",
            reason=(
                f"{initial.clause_id}: admission was {served_days} days after the policy "
                f"began, inside the {initial.days}-day waiting period, so nothing is payable"
            ),
        )

    ped = _period(policy, "ped")
    note = (
        f"{served_months} months of coverage at admission; no waiting period applies"
        if not condition
        else (
            f"{condition} is on the specified-disease list, but {served_months} months "
            f"had elapsed and the period is {specified.months if specified else '?'} months"
        )
    )
    if ped:
        note += (
            f". {ped.clause_id} excludes pre-existing disease for {ped.months} months; "
            "nothing on a bill states whether a condition pre-existed the policy, so that "
            "was not assessed"
        )
    return WaitingVerdict(excluded=False, note=note)
