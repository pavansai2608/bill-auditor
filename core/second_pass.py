"""The second pass: one breached room rent rewrites every other eligible line.

Judging lines one at a time can never find this. Nothing in the surgeon's-fee
line mentions room rent, yet if the room billed above its per-day cap the
policy reduces the surgeon's fee - and the nursing charges, and the operation
theatre - in the same proportion. That is why the audit runs a second time over
the verdicts it already has.

    ratio = eligible room rent per day / room rent actually charged per day

Two rules keep it honest:

* **Python does the arithmetic.** The model is not asked to rescale anything,
  or even asked about the ratio. It reported a limit; that is all it is for.
* **The definition decides the scope, not a guess.** Associated Medical
  Expenses is a defined term (star_health `I.Def45`, hdfc_ergo `A.1.2.Def5`,
  niva_bupa `6.2.4`) and it names both what is reached - nursing, operation
  theatre, the practitioners' fees - and what is not: pharmacy and consumables,
  implants and medical devices, diagnostics, and ICU charges. An item the
  definition does not name is left alone and said so in the trace. Rescaling a
  line the policy never put inside the deduction is a silent overcharge to the
  insured.
"""

import re

from core.assumptions import Assumptions
from core.ingest import load_clauses
from core.logging_conf import get_logger
from core.models import BillLine, Clause, LineVerdict
from core.money import proportionate_ratio

log = get_logger(__name__)

# The clause that states the deduction, not the one that defines the term.
PROPORTIONATE_RE = re.compile(r"proportionate deduction", re.I)
# star_health I.Def45 and hdfc_ergo A.1.2.Def5 both carry the phrase, but they
# define Associated Medical Expenses; the operative statement is in the
# coverage clause. Prefer the clause that applies the rule.
DEFINITION_ID_RE = re.compile(r"\.Def\d+$", re.I)

# What the definition reaches.
AME_RE = re.compile(
    r"nursing|operation theatre|\bot charges\b|surgeon|assistant surgeon|"
    r"an(?:a)?esthet|an(?:a)?esthesia|physician|specialist|consultant|consultation|"
    r"professional fee|doctor(?:'s)? (?:fee|visit)|surgical appliance|blood|oxygen",
    re.I,
)

# What it explicitly does not, in every one of the three policies. Checked
# first: "ICU nursing charges" is an ICU charge, not a nursing charge.
NOT_AME_RE = re.compile(
    r"\bicu\b|intensive care|ventilator|"
    r"pharmac|medicine|drug|consumable|"
    r"implant|prosthe|\blens\b|\bmesh\b|\bstent\b|medical device|"
    r"diagnostic|investigation|x-?ray|\bmri\b|\bct\b|ultrasound|sonograph|"
    r"angiogram|endoscopy|biopsy|patholog|radiolog|\blab\b|\blabs\b|blood panel",
    re.I,
)

ROOM_RE = re.compile(r"room rent|room charges|bed charges|accommodation", re.I)

INCLUDED, EXCLUDED, UNNAMED = "included", "excluded", "unnamed"


def classify_for_ame(item: str) -> str:
    """Is this line inside Associated Medical Expenses, outside it, or unnamed?

    Exclusion is tested first because the excluded terms are the specific ones:
    "ICU nursing charges" is an ICU charge the definition removes, not a
    nursing charge it reaches.
    """
    if ROOM_RE.search(item) or NOT_AME_RE.search(item):
        return EXCLUDED
    if AME_RE.search(item):
        return INCLUDED
    return UNNAMED


def find_proportionate_clause(policy: str) -> Clause | None:
    """The clause to cite for the deduction, found deterministically.

    No retrieval and no model call: the ratio is arithmetic, and the clause
    that authorises it is the same clause every time for a given policy.
    """
    matches = [c for c in load_clauses() if c.policy == policy and PROPORTIONATE_RE.search(c.text)]
    if not matches:
        return None
    operative = [c for c in matches if not DEFINITION_ID_RE.search(c.clause_id)]
    return (operative or matches)[0]


def breach_ratio(lines: list[BillLine], verdicts: list[LineVerdict]) -> tuple[float, str | None]:
    """The ratio the breached **room** line imposes, and the item that imposed it.

    `over_limit` is set by any breached per-day cap, and only a breached *room
    rent* cap triggers a proportionate deduction. The distinction is not
    academic: on B01 the judge marked "ICU Charges 12,000 x 2 days" as over a
    5,000/day limit and the pass took its 0.4167 as the ratio, cutting the
    surgeon's fee by a rule about a room the insured never breached. ICU is not
    room rent - Def45 excludes it by name - and on B04 the source was a surgeon
    fee. Both produced a confident, fully cited, wrong deduction.

    Where more than one room line breached, the lowest ratio wins: the insured
    cannot be better off for having been billed the same room twice.
    """
    ratio, source = 1.0, None
    for line, verdict in zip(lines, verdicts, strict=True):
        if not verdict.over_limit or verdict.limit_per_day is None:
            continue
        if not ROOM_RE.search(verdict.item):
            log.info(
                "ignoring a per-day breach on %r: only room rent drives a proportionate deduction",
                verdict.item,
            )
            continue
        charged_rate = verdict.charged / max(line.qty, 1)
        candidate = proportionate_ratio(verdict.limit_per_day, charged_rate)
        if candidate < ratio:
            ratio, source = candidate, verdict.item
    return ratio, source


def apply(
    lines: list[BillLine],
    verdicts: list[LineVerdict],
    policy: str,
    assumptions: Assumptions | None = None,
) -> tuple[list[LineVerdict], list[dict]]:
    """Rescale the associated medical expenses. Returns new verdicts and trace.

    Nothing is mutated in place: a verdict that is not rescaled comes back as
    the same object, so a caller can tell what the pass touched.
    """
    assumptions = assumptions or Assumptions()
    ratio, source = breach_ratio(lines, verdicts)

    if ratio >= 1.0:
        return verdicts, [
            {"node": "second_pass", "applied": False, "why": "no per-day cap was breached"}
        ]

    if not assumptions.differential_billing:
        # The policy disapplies the deduction at hospitals that do not bill
        # differentially. The assumption was turned off, so it does not apply.
        return verdicts, [
            {
                "node": "second_pass",
                "applied": False,
                "why": "differential billing was ruled out, so proportionate deduction does not apply",
                "ratio": round(ratio, 4),
            }
        ]

    clause = find_proportionate_clause(policy)
    if clause is None:
        # Without a clause there is no citation, and an uncited deduction is
        # exactly what this project exists not to produce.
        return verdicts, [
            {
                "node": "second_pass",
                "applied": False,
                "why": f"no proportionate-deduction clause found in {policy}",
                "ratio": round(ratio, 4),
            }
        ]

    trace: list[dict] = [
        {
            "node": "second_pass",
            "applied": True,
            "ratio": round(ratio, 4),
            "because": source,
            "clause_id": clause.clause_id,
        }
    ]

    updated: list[LineVerdict] = []
    for verdict in verdicts:
        scope = classify_for_ame(verdict.item)
        untouched = (
            verdict.allowed is None  # flagged, or settled without an amount
            or verdict.needs_human
            or verdict.over_limit  # the room line itself: capped, not rescaled
            or scope != INCLUDED
        )
        if untouched:
            trace.append(
                {
                    "node": "second_pass",
                    "item": verdict.item,
                    "rescaled": False,
                    "scope": scope,
                    "why": _why_untouched(verdict, scope),
                }
            )
            updated.append(verdict)
            continue

        before = verdict.allowed
        after = round(before * ratio, 2)
        updated.append(
            verdict.model_copy(
                update={
                    "allowed": after,
                    "clause_id": clause.clause_id,
                    "reason": (
                        f"room rent exceeded its per-day limit, so this associated medical "
                        f"expense is reduced in the same proportion: "
                        f"{before:,.2f} x {ratio:.4f} = {after:,.2f} ({clause.clause_id})"
                    ),
                }
            )
        )
        trace.append(
            {
                "node": "second_pass",
                "item": verdict.item,
                "rescaled": True,
                "scope": scope,
                "before": before,
                "after": after,
                "clause_id": clause.clause_id,
            }
        )

    rescaled = sum(1 for entry in trace if entry.get("rescaled"))
    log.info(
        "second pass: ratio %.4f from %r, rescaled %d line(s) under %s",
        ratio,
        source,
        rescaled,
        clause.clause_id,
    )
    return updated, trace


def _why_untouched(verdict: LineVerdict, scope: str) -> str:
    if verdict.needs_human or verdict.allowed is None:
        return "flagged for human review, so there is no amount to rescale"
    if verdict.over_limit:
        return "this is the room line itself, already capped at its per-day limit"
    if scope == EXCLUDED:
        return "outside associated medical expenses, so the deduction does not reach it"
    return "the definition of associated medical expenses does not name this item"
