"""Look-up aid for filling in the answer key by hand.

Prints one bill, then the clauses from that bill's policy that could plausibly
decide it. It deliberately does not run the retriever, the judge or any model,
and it does not rank, score or suggest anything: the answer key is the ground
truth the system is measured against, so if it were derived from the system
the evaluation would only prove the system agrees with itself.

    uv run python eval/helper.py B01                 # bill + an index of candidate clauses
    uv run python eval/helper.py B01 --clause II.1   # read one clause in full
    uv run python eval/helper.py B01 --text          # every candidate clause, with text
    uv run python eval/helper.py B01 --text --full   # ... untruncated
    uv run python eval/helper.py B01 --grep room     # clauses matching a pattern
    uv run python eval/helper.py B01 --all           # every clause, not just deciding ones
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BILLS_DIR = ROOT / "eval" / "bills"
CLAUSES = ROOT / "data" / "clauses.json"
NON_PAYABLE = ROOT / "data" / "non_payable.json"

# The rule types that decide money. "other" is definitions and administration.
DECIDING = ("room_rent", "sub_limit", "copay", "waiting_period", "non_payable")
RULE = "─" * 78
# Clause bodies run to thousands of characters. Truncated by default so a bill
# fits on one screen; --full or --clause shows the whole thing.
PREVIEW_CHARS = 420


def load_bill(bill_id: str) -> dict:
    path = BILLS_DIR / f"{bill_id.upper()}.json"
    if not path.exists():
        raise SystemExit(f"no such bill: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def print_bill(bill: dict) -> None:
    print(RULE)
    print(f"{bill['bill_id']}   policy: {bill['policy']}   sum insured: Rs {bill['sum_insured']:,}")
    print(
        f"        policy start: {bill['policy_start_date']}   "
        f"admitted: {bill['admission_date']}   discharged: {bill['discharge_date']}"
    )
    schedule = bill.get("policy_schedule")
    if schedule:
        parts = []
        if schedule.get("room_limit_per_day") is not None:
            parts.append(f"room limit Rs {schedule['room_limit_per_day']:,.0f}/day")
        if schedule.get("room_category"):
            parts.append(f"room category {schedule['room_category']}")
        print(f"        policy schedule: {', '.join(parts)}")
    else:
        print("        policy schedule: NOT PROVIDED - a room limit that depends on it")
        print("                         must come back needs_human, not a guess")
    print(f"        category: {bill['category']}")
    print(RULE)
    print(f"{'#':>3}  {'item':<52}{'qty':>5}{'charged':>14}")
    for index, line in enumerate(bill["lines"], start=1):
        print(f"{index:>3}  {line['item'][:52]:<52}{line['qty']:>5}{line['amount']:>14,.2f}")
    print(f"{'':>3}  {'TOTAL CHARGED':<52}{'':>5}{bill['total_charged']:>14,.2f}")


def _body(text: str, *, full: bool) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if full:
        return paragraphs
    out: list[str] = []
    used = 0
    for paragraph in paragraphs:
        if used >= PREVIEW_CHARS:
            out.append("... (--full for the rest)")
            break
        remaining = PREVIEW_CHARS - used
        if len(paragraph) > remaining:
            out.append(paragraph[:remaining] + " ... (--full for the rest)")
            break
        out.append(paragraph)
        used += len(paragraph)
    return out


def print_clauses(
    policy: str,
    *,
    show_all: bool,
    grep: str | None,
    full: bool,
    only: str | None,
    text: bool,
) -> None:
    if not CLAUSES.exists():
        raise SystemExit("data/clauses.json not found - run 'uv run python -m core.ingest'")
    clauses = [c for c in json.loads(CLAUSES.read_text(encoding="utf-8")) if c["policy"] == policy]

    if only:
        clauses = [c for c in clauses if c["clause_id"].lower() == only.lower()]
        heading = f"clause {only} in {policy}"
        full = True
        text = True
    elif grep:
        pattern = re.compile(grep, re.I)
        clauses = [c for c in clauses if pattern.search(c["text"]) or pattern.search(c["title"])]
        heading = f"clauses in {policy} matching /{grep}/"
        text = True
    elif show_all:
        heading = f"all clauses in {policy}"
    else:
        clauses = [c for c in clauses if c["rule_type"] in DECIDING]
        heading = f"clauses in {policy} of type: {', '.join(DECIDING)}"

    print()
    print(RULE)
    print(f"{heading}   ({len(clauses)} found)")
    print(RULE)

    if not text:
        # An index, not a dump. Twenty-eight clauses printed in full is three
        # screens per bill and forty bills to get through; scan this, then open
        # the one you want with --clause.
        print(f"{'clause':<14}{'pg':>4}  {'type':<15} title")
        for clause in clauses:
            title = clause["title"].replace("\n", " ")[:44]
            print(
                f"{clause['clause_id']:<14}{clause['page']:>4}  {clause['rule_type']:<15} {title}"
            )
        print("\nread one with:  --clause <id>      all of them with:  --text")
        return

    for clause in clauses:
        print(f"\n[{clause['clause_id']}]  p{clause['page']}  ({clause['rule_type']})")
        print(f"  {clause['title']}")
        for paragraph in _body(clause["text"], full=full):
            print(f"    {paragraph}")


def print_non_payable(bill: dict, *, show_all: bool) -> None:
    """Show the IRDAI list, narrowed to entries whose wording appears in this bill.

    A filter, not a verdict. It surfaces which of the 68 entries are worth
    reading for this bill; whether a given line is actually non-payable is still
    a judgement, and a near-miss (syringes are not on the list, gloves are) is
    exactly the kind of call the key has to make.
    """
    if not NON_PAYABLE.exists():
        return
    items = json.loads(NON_PAYABLE.read_text(encoding="utf-8"))

    if show_all:
        shown, heading = items, f"IRDAI non-payable list - all {len(items)} entries"
    else:
        billed = " | ".join(line["item"].lower() for line in bill["lines"])
        shown = [i for i in items if re.split(r"[(/-]", i)[0].strip().lower() in billed]
        heading = (
            f"IRDAI non-payable list - {len(shown)} of {len(items)} entries "
            f"whose wording appears in this bill (--list-all for every entry)"
        )

    print()
    print(RULE)
    print(f"{heading}   cite as IRDAI-List-I")
    print(RULE)
    if not shown:
        print("  (no entry matches this bill by name - check the full list to be sure)")
    for index in range(0, len(shown), 2):
        print("  " + " | ".join(f"{i:<36}" for i in shown[index : index + 2]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Show a bill and its policy's deciding clauses")
    parser.add_argument("bill_id", help="e.g. B01")
    parser.add_argument(
        "--all", action="store_true", help="show every clause, not just deciding ones"
    )
    parser.add_argument("--grep", help="only clauses whose title or text matches this pattern")
    parser.add_argument("--text", action="store_true", help="print clause text, not just an index")
    parser.add_argument("--full", action="store_true", help="with --text, do not truncate")
    parser.add_argument("--clause", help="print just this clause, in full")
    parser.add_argument("--list-all", action="store_true", help="print all 68 IRDAI entries")
    parser.add_argument("--no-list", action="store_true", help="skip the IRDAI non-payable list")
    args = parser.parse_args()

    bill = load_bill(args.bill_id)
    print_bill(bill)
    print_clauses(
        bill["policy"],
        show_all=args.all,
        grep=args.grep,
        full=args.full,
        only=args.clause,
        text=args.text,
    )
    if not args.no_list:
        print_non_payable(bill, show_all=args.list_all)
    print()
    print(RULE)
    print("Fill these in by hand in eval/answer_key.json. Do not run the auditor to get them.")
    print(RULE)


if __name__ == "__main__":
    main()
