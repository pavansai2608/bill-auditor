"""Naive audit - the deliberately simple baseline (v0).

One search per line, one judge call, Python does the arithmetic. No retry when
the model is unsure, no query rewriting, no abstention beyond a failed lookup,
and no second pass. It will get things wrong.

That is the point. Building the agent first would leave no way to show it
helped; Phase 5 measures this, and every later version is measured against it.
The one rule not relaxed is citation integrity: a clause_id the model invents
is rejected here exactly as it will be later, because a fabricated citation is
the worst output this system can produce.
"""

import re

from core.assumptions import Assumptions
from core.ingest import load_clauses
from core.llm import LLMError, complete_structured
from core.logging_conf import get_logger
from core.models import AuditReport, BillLine, JudgeOutput, Limit, LineVerdict, PolicySchedule
from core.money import allowed_for_line, per_day_limit
from core.retrieve import RetrievedClause, search

log = get_logger(__name__)

# A clause that hands the number to the policy schedule instead of stating it.
SCHEDULE_DEFERRAL_RE = re.compile(
    r"(?:specified|stipulated|mentioned|opted)\s+(?:by you\s+)?in\s+(?:the\s+|your\s+)?Policy\s+Schedule"
    r"|as per the limits.{0,30}Policy Schedule",
    re.I,
)

# A clause can name the schedule and still decide the question. HDFC says
# "Room rent limit shall be 'At Actuals' unless otherwise specified in the
# Policy Schedule" - absent a schedule, At Actuals is what the policy says
# applies. That is an answer, not a gap, so it must not trigger an abstention.
# Niva Bupa states no such fallback, which is why it still abstains.
STATES_A_DEFAULT_RE = re.compile(r"At Actuals", re.I)
SCHEDULE_MISSING_REASON = "room limit is set by the policy schedule, which was not provided"

# The carve-out that makes proportionate deduction conditional on a fact no
# bill carries.
DIFFERENTIAL_BILLING_RE = re.compile(
    r"(?:not\s+(?:be\s+)?appl(?:ied|icable)|shall not apply).{0,120}differential billing"
    r"|differential billing.{0,120}not (?:followed|adopted|applicable)",
    re.I,
)


def differential_billing_carve_out(policy: str) -> tuple[str | None, str | None]:
    """Find the clause that disapplies proportionate deduction, to quote it."""
    for clause in load_clauses():
        if clause.policy == policy and DIFFERENTIAL_BILLING_RE.search(clause.text):
            match = DIFFERENTIAL_BILLING_RE.search(clause.text)
            start = max(0, match.start() - 120)
            return clause.clause_id, clause.text[start : match.end() + 120].strip()
    return None, None


JUDGE_SYSTEM = """You read insurance policy clauses and report what limits apply to a bill item.

You NEVER calculate an amount. You report the limits exactly as the clause states
them; the amount is computed separately.

Return one entry in `limits` for EVERY limit the clause states for this item.
A clause often states more than one, and all of them apply:
  "Rs.750/- per hospitalization and Rs.1,500/- per Policy Period"
    -> two entries: {amount: 750, basis: "per_hospitalization"}
                    {amount: 1500, basis: "per_policy_period"}
  "10% of Sum Insured or Rs 1,00,000, whichever is less"
    -> two entries: {percentage: 10, of: "sum_insured", basis: "absolute"}
                    {amount: 100000, basis: "absolute"}
  "room rent up to Rs 5,000 per day"
    -> one entry:   {amount: 5000, basis: "per_day"}

basis must be one of: per_day, per_hospitalization, per_policy_period, absolute.
Use `amount` for a rupee figure, or `percentage` with of="sum_insured" for a
percentage. Never both in the same entry.

Return an empty `limits` list when the clause allows the item in full.
For an item the policy excludes entirely, return {amount: 0, basis: "absolute"}.

If a policy schedule figure is given above, report it as a limit.
If the clause defers the limit to the Policy Schedule and no schedule figure is
given, return an empty `limits` list - do not invent or assume one.

clause_id must be copied exactly from one of the clauses shown. Never invent one.

Set confident to false when none of the clauses shown actually decides this item.
It is far better to say you are unsure than to cite a clause that does not apply."""


def _judge_prompt(
    line: BillLine,
    candidates: list[RetrievedClause],
    sum_insured: float,
    schedule: PolicySchedule | None = None,
) -> str:
    blocks = [
        f"clause_id: {c.clause.clause_id}\ntitle: {c.clause.title}\ntext: {c.matched_text}"
        for c in candidates
    ]
    schedule_text = ""
    if schedule and not schedule.is_empty():
        parts = []
        if schedule.room_limit_per_day is not None:
            parts.append(f"room rent limit Rs {schedule.room_limit_per_day:,.0f} per day")
        if schedule.room_category:
            parts.append(f"room category {schedule.room_category}")
        schedule_text = "Policy schedule states: " + "; ".join(parts) + "\n"
    return (
        schedule_text + f"Sum insured: Rs {sum_insured:,.0f}\n"
        f"Bill item: {line.item}\n"
        f"Amount charged: Rs {line.amount:,.2f}\n"
        f"Quantity/days: {line.qty}\n\n"
        f"Policy clauses:\n\n" + "\n\n---\n\n".join(blocks)
    )


def _build_query(line: BillLine) -> str:
    """The naive query: the item name and nothing else.

    Phase 6 replaces this with rule-type routing and rewriting on failure.
    """
    return f"{line.item} limit coverage"


def _defers_to_schedule(candidates: list[RetrievedClause]) -> bool:
    """True only where the clause hands over the figure and offers no fallback."""
    return any(
        SCHEDULE_DEFERRAL_RE.search(c.matched_text)
        and not STATES_A_DEFAULT_RE.search(c.matched_text)
        for c in candidates
    )


def audit_line(
    line: BillLine,
    policy: str,
    sum_insured: float,
    valid_ids: set[str],
    schedule: PolicySchedule | None = None,
) -> LineVerdict:
    candidates = search(_build_query(line), policy)

    if not candidates:
        return LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=None,
            reason="no policy clause was retrieved for this item",
            needs_human=True,
        )

    try:
        judge = complete_structured(
            _judge_prompt(line, candidates, sum_insured, schedule),
            JudgeOutput,
            system=JUDGE_SYSTEM,
        )
    except LLMError as exc:
        log.warning("judge failed for %r: %s", line.item, exc)
        return LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=None,
            reason="the model could not produce a usable verdict",
            needs_human=True,
        )

    if not judge.confident:
        return LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=judge.clause_id,
            reason=judge.reasoning or "no clause clearly covers this item",
            needs_human=True,
        )

    # Hard rule: the citation must exist. Naive means no retry, not no checking.
    if judge.clause_id not in valid_ids:
        log.warning("rejected fabricated clause_id %r for %r", judge.clause_id, line.item)
        return LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=None,
            reason=f"cited clause {judge.clause_id!r} does not exist in this policy",
            needs_human=True,
        )

    # The clause hands the figure to the policy schedule and none was given.
    # Saying so is the honest answer; picking a default would be a guess that
    # looks like a verdict.
    no_limit_found = not judge.limits
    schedule_given = schedule is not None and not schedule.is_empty()
    if no_limit_found and not schedule_given and _defers_to_schedule(candidates):
        return LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=judge.clause_id,
            reason=SCHEDULE_MISSING_REASON,
            needs_human=True,
        )

    # A schedule limit supplies the number the wording deliberately omits.
    if no_limit_found and schedule_given and schedule.room_limit_per_day is not None:
        judge = judge.model_copy(
            update={"limits": [Limit(amount=schedule.room_limit_per_day, basis="per_day")]}
        )

    allowed, over_limit = allowed_for_line(line, judge, sum_insured)
    return LineVerdict(
        item=line.item,
        charged=line.amount,
        allowed=allowed,
        clause_id=judge.clause_id,
        reason=judge.reasoning,
        over_limit=over_limit,
        limit_per_day=per_day_limit(judge),
    )


def audit_lines(
    lines: list[BillLine],
    policy: str,
    sum_insured: float,
    schedule: PolicySchedule | None = None,
    assumptions: Assumptions | None = None,
    use_agent: bool = False,
) -> AuditReport:
    """Judge each line independently. Nothing here looks across lines.

    `use_agent` swaps the single-shot path (v0) for the retry loop (v2). Both
    stay callable so the baseline remains reproducible: a number you cannot
    re-measure is not a baseline.
    """
    valid_ids = {c.clause_id for c in load_clauses() if c.policy == policy}
    if not valid_ids:
        raise ValueError(f"no clauses indexed for policy {policy!r}")

    assumptions = assumptions or Assumptions()
    clause_id, quote = differential_billing_carve_out(policy)
    if quote:
        assumptions.note_differential_billing(clause_id, quote)

    trace: list[dict] = list(assumptions.as_trace())
    if use_agent:
        from core.agent import audit_line as agent_audit_line

        verdicts = []
        for line in lines:
            verdict, line_trace = agent_audit_line(line, policy, sum_insured, valid_ids, schedule)
            verdicts.append(verdict)
            trace.extend(line_trace)
    else:
        verdicts = [audit_line(line, policy, sum_insured, valid_ids, schedule) for line in lines]

    return AuditReport(
        lines=verdicts,
        total_charged=round(sum(v.charged for v in verdicts), 2),
        total_allowed=round(sum(v.allowed or 0 for v in verdicts), 2),
        flagged_count=sum(1 for v in verdicts if v.needs_human),
        policy=policy,
        trace=trace,
    )


def audit_bill(
    bill_text: str,
    policy: str,
    sum_insured: float,
    policy_start_date: str | None = None,
    schedule: PolicySchedule | None = None,
    assumptions: Assumptions | None = None,
    use_agent: bool = False,
) -> AuditReport:
    """Full naive path: parse the bill, then judge every line.

    `policy_start_date` is accepted but unused at v0 - waiting periods need it,
    and they arrive with the agent in Phase 6.
    """
    from core.bill import parse_bill

    lines = parse_bill(bill_text)
    return audit_lines(lines, policy, sum_insured, schedule, assumptions, use_agent)


def format_report(report: AuditReport) -> str:
    rows = [
        f"{'item':<38} {'charged':>12} {'allowed':>12}  clause",
        "-" * 84,
    ]
    for line in report.lines:
        allowed = "FLAGGED" if line.allowed is None else f"{line.allowed:,.2f}"
        rows.append(
            f"{line.item[:38]:<38} {line.charged:>12,.2f} {allowed:>12}  {line.clause_id or '-'}"
        )
    rows += [
        "-" * 84,
        f"{'TOTAL':<38} {report.total_charged:>12,.2f} {report.total_allowed:>12,.2f}",
        f"flagged for human review: {report.flagged_count}",
    ]
    # Assumptions are printed, not buried in the trace. A reader has to be able
    # to see what was taken on trust.
    noted = [e for e in report.trace if e.get("assumption")]
    if noted:
        rows.append("")
        rows.append("ASSUMPTIONS")
        for entry in noted:
            rows.append(f"  - {entry['statement']}")
            rows.append(f"    because {entry['because']}")
            if entry.get("clause_id"):
                rows.append(f"    clause {entry['clause_id']}: {entry['clause_text'][:160]}...")
    return "\n".join(rows)


def main() -> None:
    import argparse
    from pathlib import Path

    from core.logging_conf import setup_logging

    parser = argparse.ArgumentParser(description="Audit a bill against one policy (naive v0)")
    parser.add_argument("bill", type=Path, help="path to a bill text file")
    parser.add_argument("--policy", default="star_health")
    parser.add_argument("--sum-insured", type=float, default=500000)
    args = parser.parse_args()

    setup_logging()
    report = audit_bill(args.bill.read_text(encoding="utf-8"), args.policy, args.sum_insured)
    print()
    print(format_report(report))


if __name__ == "__main__":
    main()
