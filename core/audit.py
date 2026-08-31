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

from core.ingest import load_clauses
from core.llm import LLMError, complete_structured
from core.logging_conf import get_logger
from core.models import AuditReport, BillLine, JudgeOutput, LineVerdict
from core.money import allowed_for_line
from core.retrieve import RetrievedClause, search

log = get_logger(__name__)

JUDGE_SYSTEM = """You read insurance policy clauses and report what limit applies to a bill item.

You NEVER calculate an amount. You report the limit and the clause it comes from;
the amount is computed separately.

Fill in exactly one limit field when the clause states one:
- limit_per_day    : a cap per day (room rent of Rs 5000 per day -> 5000)
- limit_absolute   : a fixed rupee cap for the whole item
- percentage       : a cap expressed as a percentage of the sum insured

Leave all three null when the clause allows the item in full, or when it excludes
the item entirely (an excluded item is limit_absolute 0).

clause_id must be copied exactly from one of the clauses shown. Never invent one.

Set confident to false when none of the clauses shown actually decides this item.
It is far better to say you are unsure than to cite a clause that does not apply."""


def _judge_prompt(line: BillLine, candidates: list[RetrievedClause], sum_insured: float) -> str:
    blocks = [
        f"clause_id: {c.clause.clause_id}\ntitle: {c.clause.title}\ntext: {c.matched_text}"
        for c in candidates
    ]
    return (
        f"Sum insured: Rs {sum_insured:,.0f}\n"
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


def audit_line(
    line: BillLine,
    policy: str,
    sum_insured: float,
    valid_ids: set[str],
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
            _judge_prompt(line, candidates, sum_insured), JudgeOutput, system=JUDGE_SYSTEM
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

    allowed, over_limit = allowed_for_line(line, judge, sum_insured)
    return LineVerdict(
        item=line.item,
        charged=line.amount,
        allowed=allowed,
        clause_id=judge.clause_id,
        reason=judge.reasoning,
        over_limit=over_limit,
        limit_per_day=judge.limit_per_day,
    )


def audit_lines(
    lines: list[BillLine],
    policy: str,
    sum_insured: float,
) -> AuditReport:
    """Judge each line independently. Nothing here looks across lines."""
    valid_ids = {c.clause_id for c in load_clauses() if c.policy == policy}
    if not valid_ids:
        raise ValueError(f"no clauses indexed for policy {policy!r}")

    verdicts = [audit_line(line, policy, sum_insured, valid_ids) for line in lines]

    return AuditReport(
        lines=verdicts,
        total_charged=round(sum(v.charged for v in verdicts), 2),
        total_allowed=round(sum(v.allowed or 0 for v in verdicts), 2),
        flagged_count=sum(1 for v in verdicts if v.needs_human),
        policy=policy,
    )


def audit_bill(
    bill_text: str,
    policy: str,
    sum_insured: float,
    policy_start_date: str | None = None,
) -> AuditReport:
    """Full naive path: parse the bill, then judge every line.

    `policy_start_date` is accepted but unused at v0 - waiting periods need it,
    and they arrive with the agent in Phase 6.
    """
    from core.bill import parse_bill

    lines = parse_bill(bill_text)
    return audit_lines(lines, policy, sum_insured)


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
