"""Look-up aid for filling in the answer key by hand.

Prints one bill, then the clauses from that bill's policy that could plausibly
decide it. It deliberately does not run the retriever, the judge or any model,
and it does not rank, score or suggest anything: the answer key is the ground
truth the system is measured against, so if it were derived from the system
the evaluation would only prove the system agrees with itself.

    uv run python eval/helper.py B01
    uv run python eval/helper.py B01 --all        # every clause, not just rule types
    uv run python eval/helper.py B01 --grep room  # clauses whose text matches
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
    print(f"        category: {bill['category']}")
    print(RULE)
    print(f"{'#':>3}  {'item':<52}{'qty':>5}{'charged':>14}")
    for index, line in enumerate(bill["lines"], start=1):
        print(f"{index:>3}  {line['item'][:52]:<52}{line['qty']:>5}{line['amount']:>14,.2f}")
    print(f"{'':>3}  {'TOTAL CHARGED':<52}{'':>5}{bill['total_charged']:>14,.2f}")


def print_clauses(policy: str, *, show_all: bool, grep: str | None) -> None:
    if not CLAUSES.exists():
        raise SystemExit("data/clauses.json not found - run 'uv run python -m core.ingest'")
    clauses = [c for c in json.loads(CLAUSES.read_text(encoding="utf-8")) if c["policy"] == policy]

    if grep:
        pattern = re.compile(grep, re.I)
        clauses = [c for c in clauses if pattern.search(c["text"]) or pattern.search(c["title"])]
        heading = f"clauses in {policy} matching /{grep}/"
    elif show_all:
        heading = f"all clauses in {policy}"
    else:
        clauses = [c for c in clauses if c["rule_type"] in DECIDING]
        heading = f"clauses in {policy} of type: {', '.join(DECIDING)}"

    print()
    print(RULE)
    print(f"{heading}   ({len(clauses)} found)")
    print(RULE)
    for clause in clauses:
        print(f"\n[{clause['clause_id']}]  p{clause['page']}  ({clause['rule_type']})")
        print(f"  {clause['title']}")
        for paragraph in clause["text"].split("\n"):
            if paragraph.strip():
                print(f"    {paragraph.strip()}")


def print_non_payable() -> None:
    if not NON_PAYABLE.exists():
        return
    items = json.loads(NON_PAYABLE.read_text(encoding="utf-8"))
    print()
    print(RULE)
    print(f"IRDAI non-payable list ({len(items)} items) - cite as IRDAI-List-I")
    print(RULE)
    for index in range(0, len(items), 3):
        print("  " + " | ".join(f"{i:<34}" for i in items[index : index + 3]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Show a bill and its policy's deciding clauses")
    parser.add_argument("bill_id", help="e.g. B01")
    parser.add_argument(
        "--all", action="store_true", help="show every clause, not just deciding ones"
    )
    parser.add_argument("--grep", help="only clauses whose title or text matches this pattern")
    parser.add_argument("--no-list", action="store_true", help="skip the IRDAI non-payable list")
    args = parser.parse_args()

    bill = load_bill(args.bill_id)
    print_bill(bill)
    print_clauses(bill["policy"], show_all=args.all, grep=args.grep)
    if not args.no_list:
        print_non_payable()
    print()
    print(RULE)
    print("Fill these in by hand in eval/answer_key.json. Do not run the auditor to get them.")
    print(RULE)


if __name__ == "__main__":
    main()
