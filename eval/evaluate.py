"""Measure the auditor against the hand-written answer key.

Every metric here is deterministic: a number is right or it is not, a clause id
matches or it does not. Nothing is scored by a model. An LLM judging its own
output would tell us the system agrees with itself, which is not a finding.

Lines whose `allowed` is still null in the key are skipped and counted, so this
is useful while the key is only half filled.

    uv run python eval/evaluate.py
    uv run python eval/evaluate.py --quick --threshold 0.80   # the CI gate
    uv run python eval/evaluate.py --version v1 --write       # record a row

The threshold makes this usable with `git bisect run`: it exits 1 when line
accuracy falls below the value given.
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent import IRDAI_CITATION
from core.assumptions import Assumptions
from core.ingest import load_clauses, load_non_payable
from core.logging_conf import setup_logging
from core.models import BillLine, PolicySchedule

ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = ROOT / "eval" / "answer_key.json"
RESULTS_PATH = ROOT / "eval" / "results.md"
QUICK_BILLS = 10
# "within Rs 1" - a rupee of rounding is not a wrong answer.
AMOUNT_TOLERANCE = 1.0


@dataclass
class Counts:
    """One tally, reusable for the whole run and for each category."""

    lines_scored: int = 0
    lines_skipped: int = 0

    amount_right: int = 0
    citation_right: int = 0
    citation_scored: int = 0

    should_abstain: int = 0
    did_abstain: int = 0
    abstained_correctly: int = 0
    false_answers: int = 0  # answered where the key says abstain
    false_abstentions: int = 0  # abstained where the key has an answer

    fabricated: int = 0
    charged_total: float = 0.0
    expected_total: float = 0.0
    computed_total: float = 0.0

    def ratio(self, top: int, bottom: int) -> float | None:
        return top / bottom if bottom else None

    @property
    def line_accuracy(self) -> float | None:
        return self.ratio(self.amount_right, self.lines_scored)

    @property
    def citation_accuracy(self) -> float | None:
        return self.ratio(self.citation_right, self.citation_scored)

    @property
    def abstention_recall(self) -> float | None:
        """Of the lines that should have been flagged, how many were."""
        return self.ratio(self.abstained_correctly, self.should_abstain)

    @property
    def abstention_precision(self) -> float | None:
        """Of the lines flagged, how many genuinely could not be decided.

        The other side of it is the dodge: flagging a line the key can answer.
        """
        return self.ratio(self.abstained_correctly, self.did_abstain)

    @property
    def payout_error(self) -> float | None:
        if not self.expected_total:
            return None
        return abs(self.computed_total - self.expected_total) / self.expected_total


@dataclass
class Run:
    overall: Counts = field(default_factory=Counts)
    by_category: dict[str, Counts] = field(default_factory=lambda: defaultdict(Counts))
    latencies: list[float] = field(default_factory=list)
    tool_calls: list[int] = field(default_factory=list)
    # Retry accounting, so the loop's value is measured rather than assumed.
    attempts: list[int] = field(default_factory=list)
    fast_path_lines: int = 0
    retries_that_changed_the_answer: int = 0
    lines_needing_a_retry: int = 0
    bills_run: int = 0
    bills_unfilled: int = 0


def citable_ids(policy: str, clauses=None) -> set[str]:
    """Every citation a verdict may legitimately carry for this policy.

    The policy's own clause ids, plus `IRDAI-List-I`. The IRDAI non-payable
    list is not in `clauses.json` but it is a real, checkable source committed
    as `data/non_payable.json`, it is what the non-payable fast path cites, and
    it is what the answer key cites for the same lines. Scoring it as a
    fabrication counted 18 correct citations as the worst failure the system
    can produce - which is why this is a named function with a test on it
    rather than a set comprehension inline in `main`.
    """
    clauses = load_clauses() if clauses is None else clauses
    ids = {c.clause_id for c in clauses if c.policy == policy}
    if load_non_payable():
        ids.add(IRDAI_CITATION)
    return ids


def _calls():
    """Count retrievals and judge calls without touching production code.

    Both paths are patched. `audit.py` and `agent.py` each import `search` and
    `complete_structured` into their own namespace, so patching one module
    leaves the other uncounted - which is how an agent run came to report 0.0
    tool calls per bill while plainly making thousands.
    """
    import core.agent as agent
    import core.audit as audit

    tally = {"search": 0, "judge": 0}
    originals = [(mod, mod.search, mod.complete_structured) for mod in (audit, agent)]

    def counted(kind, real):
        def wrapper(*args, **kwargs):
            tally[kind] += 1
            return real(*args, **kwargs)

        return wrapper

    for mod, real_search, real_judge in originals:
        mod.search = counted("search", real_search)
        mod.complete_structured = counted("judge", real_judge)

    def restore():
        for mod, real_search, real_judge in originals:
            mod.search, mod.complete_structured = real_search, real_judge

    return tally, restore


def is_filled(entry: dict) -> bool:
    """A line counts as answered once it has an amount or an explicit abstention."""
    return entry.get("allowed") is not None or entry.get("needs_human") is not None


def score_bill(
    bill_id: str,
    expected: dict,
    valid_ids: set[str],
    run: Run,
    use_agent: bool = False,
    second_pass: bool = False,
) -> dict | None:
    from core.audit import audit_lines

    filled = [line for line in expected["lines"] if is_filled(line)]
    if not filled:
        run.bills_unfilled += 1
        # Still count the lines, so progress through the key is visible.
        category = expected.get("category", "uncategorised")
        for bucket in (run.overall, run.by_category[category]):
            bucket.lines_skipped += len(expected["lines"])
        return None

    lines = [
        BillLine(item=line["item"], amount=line["charged"], qty=line["qty"])
        for line in expected["lines"]
    ]
    raw_schedule = expected.get("policy_schedule")
    schedule = PolicySchedule(**raw_schedule) if raw_schedule else None

    tally, restore = _calls()
    started = time.perf_counter()
    try:
        report = audit_lines(
            lines,
            expected["policy"],
            expected["sum_insured"],
            schedule,
            Assumptions(),
            use_agent=use_agent,
            second_pass=second_pass,
        )
    finally:
        restore()
    elapsed = time.perf_counter() - started

    run.latencies.append(elapsed)
    run.tool_calls.append(tally["search"] + tally["judge"])
    run.bills_run += 1

    for entry in report.trace:
        if entry.get("node") != "summary":
            continue
        run.attempts.append(entry["attempts"])
        if entry.get("fast_path"):
            run.fast_path_lines += 1
        if entry["attempts"] > 1:
            run.lines_needing_a_retry += 1
            if entry.get("retry_changed_answer"):
                run.retries_that_changed_the_answer += 1

    category = expected.get("category", "uncategorised")
    buckets = (run.overall, run.by_category[category])

    for want, got in zip(expected["lines"], report.lines, strict=True):
        if not is_filled(want):
            for bucket in buckets:
                bucket.lines_skipped += 1
            continue

        for bucket in buckets:
            bucket.lines_scored += 1
            bucket.charged_total += want["charged"]

        wants_abstention = bool(want.get("needs_human"))
        got_abstention = bool(got.needs_human)

        for bucket in buckets:
            if wants_abstention:
                bucket.should_abstain += 1
            if got_abstention:
                bucket.did_abstain += 1
            if wants_abstention and got_abstention:
                bucket.abstained_correctly += 1
            elif wants_abstention and not got_abstention:
                bucket.false_answers += 1
            elif got_abstention and not wants_abstention:
                bucket.false_abstentions += 1

        # A citation that does not exist in the policy is the worst failure the
        # system can produce, and it is counted whatever else the line did.
        if got.clause_id and got.clause_id not in valid_ids:
            for bucket in buckets:
                bucket.fabricated += 1

        want_amount = want.get("allowed")
        if want_amount is not None:
            for bucket in buckets:
                bucket.expected_total += want_amount
                bucket.computed_total += got.allowed or 0.0
            if got.allowed is not None and abs(got.allowed - want_amount) <= AMOUNT_TOLERANCE:
                for bucket in buckets:
                    bucket.amount_right += 1
        elif wants_abstention and got_abstention:
            # Correctly declining to answer is a correct line.
            for bucket in buckets:
                bucket.amount_right += 1

        want_clause = want.get("clause_id")
        if want_clause:
            for bucket in buckets:
                bucket.citation_scored += 1
                if got.clause_id == want_clause:
                    bucket.citation_right += 1

    return {"bill_id": bill_id, "elapsed": elapsed, "calls": tally["search"] + tally["judge"]}


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render(run: Run, version: str) -> str:
    o = run.overall
    p95 = (
        statistics.quantiles(run.latencies, n=20)[-1]
        if len(run.latencies) > 1
        else (run.latencies[0] if run.latencies else 0.0)
    )
    avg_calls = statistics.mean(run.tool_calls) if run.tool_calls else 0

    rows = [
        f"### {version} - {date.today().isoformat()}",
        "",
        f"Bills run: {run.bills_run}   ",
        f"Bills with no answers filled in yet: {run.bills_unfilled}   ",
        f"Lines scored: {o.lines_scored}   Lines skipped (key not filled): {o.lines_skipped}",
        "",
        "| metric | value |",
        "|---|---|",
        f"| Line accuracy (allowed within Rs {AMOUNT_TOLERANCE:.0f}) | {pct(o.line_accuracy)} |",
        f"| Citation accuracy | {pct(o.citation_accuracy)} |",
        f"| Payout error | {pct(o.payout_error)} |",
        f"| Abstention recall (flagged when it should) | {pct(o.abstention_recall)} |",
        f"| Abstention precision (flagged and was right) | {pct(o.abstention_precision)} |",
        f"| False answers (answered, should have flagged) | {o.false_answers} |",
        f"| Dodges (flagged, key has an answer) | {o.false_abstentions} |",
        f"| **Fabricated clauses** | **{o.fabricated}** |",
        f"| p95 latency per bill | {p95:.1f}s |",
        f"| Avg tool calls per bill | {avg_calls:.1f} |",
        "",
        "| category | lines | line acc | citation acc | dodges | false answers |",
        "|---|---|---|---|---|---|",
    ]
    for name in sorted(run.by_category):
        c = run.by_category[name]
        rows.append(
            f"| {name} | {c.lines_scored} | {pct(c.line_accuracy)} | "
            f"{pct(c.citation_accuracy)} | {c.false_abstentions} | {c.false_answers} |"
        )
    if run.attempts:
        avg_attempts = statistics.mean(run.attempts)
        changed = run.retries_that_changed_the_answer
        needed = run.lines_needing_a_retry
        rows += [
            "",
            "**Retry loop**  ",
            f"Lines settled on the non-payable fast path (no search, no judge call): "
            f"{run.fast_path_lines}  ",
            f"Average attempts per line: {avg_attempts:.2f}  ",
            f"Lines that went past attempt 1: {needed}  ",
            f"...of which a later attempt actually produced an answer: **{changed}**"
            + (f" ({changed / needed * 100:.0f}%)" if needed else ""),
            "",
        ]
    rows.append("")
    return "\n".join(rows)


def write_results(text: str) -> None:
    header = (
        "# Evaluation results\n\n"
        "Every metric is deterministic - no model scores another model's output.\n"
        "The answer key is written by hand; nothing here is generated by the\n"
        "system under test.\n\n"
    )
    existing = RESULTS_PATH.read_text(encoding="utf-8") if RESULTS_PATH.exists() else header
    if not existing.startswith("# Evaluation results"):
        existing = header + existing
    RESULTS_PATH.write_text(existing.rstrip() + "\n\n" + text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the auditor against the answer key")
    parser.add_argument("--quick", action="store_true", help=f"first {QUICK_BILLS} bills only")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="exit 1 if line accuracy falls below this (for git bisect run)",
    )
    parser.add_argument("--version", default="v0", help="label for the results row")
    parser.add_argument("--write", action="store_true", help="append the row to eval/results.md")
    parser.add_argument("--bills", nargs="*", help="run only these bill ids")
    parser.add_argument("--key", type=Path, default=KEY_PATH, help="answer key to score against")
    parser.add_argument(
        "--agent", action="store_true", help="score the retry loop (v2), not the naive path (v0)"
    )
    parser.add_argument(
        "--second-pass",
        action="store_true",
        help="apply the proportionate-deduction second pass (v3)",
    )
    args = parser.parse_args()

    setup_logging("WARNING")

    if not args.key.exists():
        print(f"answer key not found at {args.key}", file=sys.stderr)
        return 2
    key = json.loads(args.key.read_text(encoding="utf-8"))["bills"]

    wanted = sorted(key)
    if args.bills:
        wanted = [b for b in wanted if b in set(args.bills)]
    if args.quick:
        wanted = wanted[:QUICK_BILLS]

    clauses = load_clauses()
    valid_by_policy = {
        policy: citable_ids(policy, clauses) for policy in {c.policy for c in clauses}
    }

    run = Run()
    for position, bill_id in enumerate(wanted, start=1):
        expected = key[bill_id]
        print(f"[{position}/{len(wanted)}] {bill_id} ({expected['policy']})", flush=True)
        score_bill(
            bill_id,
            expected,
            valid_by_policy.get(expected["policy"], set()),
            run,
            args.agent,
            args.second_pass,
        )

    report = render(run, args.version)
    print()
    print(report)

    if run.overall.lines_scored == 0:
        print("No lines scored yet - fill in some answers in eval/answer_key.json.")
        print(f"Lines waiting to be filled: {run.overall.lines_skipped}")
        return 0

    if args.write:
        write_results(report)
        print(f"appended to {RESULTS_PATH}")

    if args.threshold is not None:
        accuracy = run.overall.line_accuracy or 0.0
        if accuracy < args.threshold:
            print(
                f"FAIL: line accuracy {accuracy:.3f} is below the threshold {args.threshold:.3f}",
                file=sys.stderr,
            )
            return 1
        print(f"PASS: line accuracy {accuracy:.3f} meets the threshold {args.threshold:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
