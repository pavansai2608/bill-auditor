"""Can retrieval even see the clause the answer key names? The ceiling on accuracy.

The judge only ever reads the three clauses the reranker puts in front of it. If
the clause the key cites is not among them, no amount of prompting or retrying
can produce the right citation - the line is lost before the model is asked. So
this is the hard ceiling, and every accuracy number sits under it.

Three depths, because where the ceiling bites decides what to fix:

    candidates   the raw dense + BM25 union, before any reranking. Low here
                 means the query or the chunking is wrong, and reranking cannot
                 rescue what was never retrieved.
    recall@20    the full reranked list. High here with a low recall@3 means the
                 cross-encoder is putting the right clause below the cut.
    recall@3     what the judge actually sees.

Reported for the first query angle, which is what most lines use, and again as
the union over all three angles - the ceiling the retry loop can reach.

Lines the key answers with `IRDAI-List-I`, and lines it flags `needs_human`, are
counted separately: neither is decided by retrieval.

    uv run python eval/recall.py                 # all 44 bills
    uv run python eval/recall.py --quick         # the first 10
    uv run python eval/recall.py --out eval/recall_before.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.agent import IRDAI_CITATION, QUERY_ANGLES, RULE_PATTERNS
from core.config import settings
from core.logging_conf import setup_logging
from core.models import RuleType
from core.retrieve import (
    ClauseReranker,
    ClauseSubChunker,
    get_hybrid_retriever,
)

KEY_PATH = ROOT / "eval" / "answer_key.json"
QUICK_BILLS = 10
# Deep enough that "the reranker ranked it 30th" is visible rather than clipped.
FULL_DEPTH = 200


def classify(item: str) -> RuleType:
    """`core.agent.classify`, on a bare string. Kept in step with it by test."""
    for candidate, pattern in RULE_PATTERNS:
        if pattern.search(item):
            return candidate
    return "other"


def queries_for(item: str, rule_type: RuleType) -> list[str]:
    """Every angle `core.agent.build_query` would use, in attempt order."""
    angles = QUERY_ANGLES.get(rule_type, QUERY_ANGLES["other"])
    stripped = re.sub(r"[\d,]+\s*x\s*\d+\s*days?|\(.*?\)|[\d,]{4,}", "", item).strip()
    return [angle.format(item=stripped or item) for angle in angles]


def ranked_clause_ids(query: str, policy: str) -> tuple[list[str], set[str]]:
    """(clause ids best first after reranking, clause ids in the raw candidate set).

    The retrieval stack taken apart rather than called through `search`, because
    `search` returns only the top few and the question here is where in the list
    the right clause landed.
    """
    raw = get_hybrid_retriever(policy).invoke(query)
    candidates = {d.metadata.get("clause_id") for d in raw}
    windows = ClauseSubChunker().transform_documents(raw)
    ranked = ClauseReranker(top_n=FULL_DEPTH).compress_documents(windows, query)
    return [d.metadata.get("clause_id") for d in ranked], candidates


class Tally:
    def __init__(self) -> None:
        self.lines = 0
        self.at3 = 0
        self.at20 = 0
        self.in_candidates = 0
        self.union3 = 0

    def rate(self, top: int) -> str:
        return "n/a" if not self.lines else f"{top / self.lines * 100:.1f}%"

    def row(self, name: str) -> str:
        return (
            f"| {name} | {self.lines} | {self.rate(self.at3)} | {self.rate(self.union3)} | "
            f"{self.rate(self.at20)} | {self.rate(self.in_candidates)} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="the first 10 bills")
    parser.add_argument("--out", type=Path, help="write a markdown report here")
    parser.add_argument("--label", default="", help="a name for this measurement")
    args = parser.parse_args()

    setup_logging()
    key = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    bills = sorted(key["bills"])
    if args.quick:
        bills = bills[:QUICK_BILLS]

    overall = Tally()
    by_category: dict[str, Tally] = defaultdict(Tally)
    by_policy: dict[str, Tally] = defaultdict(Tally)
    skipped = Counter()
    misses: list[str] = []

    for number, bill_id in enumerate(bills, start=1):
        entry = key["bills"][bill_id]
        policy = entry["policy"]
        category = entry.get("category", "uncategorised")
        print(f"[{number}/{len(bills)}] {bill_id} ({policy})", flush=True)

        for line in entry["lines"]:
            want = line.get("clause_id")
            if not want:
                skipped["the key flags this line, so nothing is retrievable"] += 1
                continue
            if want == IRDAI_CITATION:
                skipped["settled on the non-payable list, no search runs"] += 1
                continue

            rule_type = classify(line["item"])
            angles = queries_for(line["item"], rule_type)

            first_ranked, first_candidates = ranked_clause_ids(angles[0], policy)
            hit3 = want in first_ranked[:3]
            union = hit3
            for angle in angles[1:]:
                if union:
                    break
                later, _ = ranked_clause_ids(angle, policy)
                union = want in later[:3]

            for tally in (overall, by_category[category], by_policy[policy]):
                tally.lines += 1
                tally.at3 += hit3
                tally.union3 += union
                tally.at20 += want in first_ranked[:20]
                tally.in_candidates += want in first_candidates

            if not union:
                place = first_ranked.index(want) + 1 if want in first_ranked else 0
                misses.append(
                    f"| {bill_id} | {line['item'][:40]} | `{want}` | {rule_type} | "
                    f"{'not retrieved at all' if not place else f'ranked {place}'} | "
                    f"`{first_ranked[0] if first_ranked else '-'}` |"
                )

    report = render(overall, by_category, by_policy, skipped, misses, args.label, len(bills))
    print("\n" + report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"written to {args.out}")
    return 0


def render(overall, by_category, by_policy, skipped, misses, label, bills) -> str:
    from core.cache import file_digest

    out = [
        f"# Retrieval recall{' - ' + label if label else ''} - {date.today().isoformat()}",
        "",
        f"{bills} bills. Clause index `{file_digest(settings.clauses_path)[:12]}`.",
        "",
        "**recall@3 is the ceiling on citation accuracy.** The judge is shown three",
        "clauses; a line whose answer is not among them cannot be got right, however",
        "the model is prompted.",
        "",
        "| scope | lines | recall@3 | recall@3 over 3 angles | recall@20 | in the candidate set |",
        "|---|---|---|---|---|---|",
        overall.row("**all**"),
    ]
    for name in sorted(by_policy):
        out.append(by_policy[name].row(name))
    out.append("")
    out += [
        "| category | lines | recall@3 | recall@3 over 3 angles | recall@20 | in the candidate set |",
        "|---|---|---|---|---|---|",
    ]
    for name in sorted(by_category):
        out.append(by_category[name].row(name))

    out += ["", "**Lines retrieval never sees**", ""]
    for reason, count in skipped.most_common():
        out.append(f"- {count} — {reason}")

    out += [
        "",
        f"## Missed by every angle — {len(misses)} lines",
        "",
        "Where the cited clause ended up. `not retrieved at all` means it was not in",
        "the reranked list at any depth, which is a candidate-set problem rather than a",
        "ranking one.",
        "",
        "| bill | line | key cites | rule type | where it ranked | what ranked first |",
        "|---|---|---|---|---|---|",
        *misses,
    ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
