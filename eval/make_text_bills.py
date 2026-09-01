"""Write every eval bill out as the plain text the UI's paste box takes.

Two jobs, and the second is the one that matters.

The first is convenience: 44 realistic bills as `.txt` files, ready to paste
into the form, plus an INDEX.md holding the dropdown values each one needs
(policy, sum insured, the two dates, and the room limit where the schedule
carries one). Without that index a bill is unauditable - the wrong sum insured
reads the wrong row out of the room rent table.

The second is a check. Every bill is stored twice: as a `lines` array that the
eval scores against, and as `bill_text` that the UI and `core.bill` parse. The
two can drift, and nothing else in the repo compares them - a bill whose text
says 8,000 and whose lines say 9,000 would score perfectly on the JSON path and
be wrong everywhere a human looks. So the text is parsed back with a regex and
compared, item by item, against the JSON.

That regex check is deliberately not the LLM parser: it is deterministic, runs
in milliseconds and can sit in the test suite. `--llm` runs the real
`core.bill.parse_bill` over all 44 instead, which is the stronger claim and
costs 44 model calls.

    uv run python eval/make_text_bills.py            # write and check
    uv run python eval/make_text_bills.py --check    # check only, write nothing
    uv run python eval/make_text_bills.py --llm      # check with the real parser
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BILLS_DIR = Path(__file__).parent / "bills"
TEXT_DIR = BILLS_DIR / "text"

# "Surgical Gloves                                20     1,200.00"
# The description may hold digits and commas of its own ("8,000 x 5 days"), so
# the split is on the run of two or more spaces before the quantity, not on the
# first digit. GRAND TOTAL has no quantity column and so never matches.
ROW_RE = re.compile(r"^(?P<item>\S.*?)\s{2,}(?P<qty>\d+)\s+(?P<amount>[\d,]+\.\d{2})\s*$")
TOTAL_RE = re.compile(r"^GRAND TOTAL\s+(?P<amount>[\d,]+\.\d{2})\s*$", re.I)


def rupees(text: str) -> float:
    return float(text.replace(",", ""))


def parse_text_bill(bill_text: str) -> tuple[list[dict[str, Any]], float | None]:
    """Read back the itemised rows and the printed total, with no model."""
    rows: list[dict[str, Any]] = []
    total: float | None = None
    for line in bill_text.splitlines():
        matched_total = TOTAL_RE.match(line.strip())
        if matched_total:
            total = rupees(matched_total.group("amount"))
            continue
        matched = ROW_RE.match(line.rstrip())
        if matched:
            rows.append(
                {
                    "item": matched.group("item").strip(),
                    "qty": int(matched.group("qty")),
                    "amount": rupees(matched.group("amount")),
                }
            )
    return rows, total


def compare(bill: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Every way the text and the JSON can disagree, as plain sentences.

    Returns problems and warnings separately. A description that the printed
    bill cut off at the column width is a warning: real bills truncate, and the
    audit turns on the amounts, not the label. Anything else - a different
    item, a different figure, a different count - is a problem, because it
    means the two halves of the fixture describe different bills.
    """
    problems: list[str] = []
    warnings: list[str] = []
    rows, printed_total = parse_text_bill(bill["bill_text"])
    lines = bill["lines"]

    if len(rows) != len(lines):
        problems.append(f"the text has {len(rows)} items, the JSON has {len(lines)}")
        return problems, warnings  # a length mismatch makes the pairwise report noise

    for position, (row, line) in enumerate(zip(rows, lines, strict=True), start=1):
        if row["item"] != line["item"]:
            if line["item"].startswith(row["item"]):
                warnings.append(
                    f"item {position}: the printed bill truncates "
                    f"{line['item']!r} to {row['item']!r}"
                )
            else:
                problems.append(f"item {position}: text {row['item']!r} vs JSON {line['item']!r}")
        if abs(row["amount"] - line["amount"]) > 0.01:
            problems.append(
                f"item {position} ({line['item']}): text {row['amount']:,.2f} "
                f"vs JSON {line['amount']:,.2f}"
            )
        if row["qty"] != line["qty"]:
            problems.append(
                f"item {position} ({line['item']}): text qty {row['qty']} vs JSON {line['qty']}"
            )

    if printed_total is None:
        problems.append("the text prints no GRAND TOTAL")
    elif abs(printed_total - bill["total_charged"]) > 0.01:
        problems.append(
            f"GRAND TOTAL {printed_total:,.2f} vs total_charged {bill['total_charged']:,.2f}"
        )
    return problems, warnings


def compare_with_llm(bill: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The stronger check: the real parser, the one the UI actually uses."""
    from core.bill import normalize_item, parse_bill

    parsed = parse_bill(bill["bill_text"])
    expected = bill["lines"]
    if len(parsed) != len(expected):
        return [f"the parser returned {len(parsed)} items, the JSON has {len(expected)}"], []

    problems: list[str] = []
    warnings: list[str] = []
    for position, (got, want) in enumerate(zip(parsed, expected, strict=True), start=1):
        wanted = normalize_item(want["item"])
        if got.item != wanted:
            if wanted.startswith(got.item):
                warnings.append(
                    f"item {position}: the printed bill truncates {wanted!r} to {got.item!r}"
                )
            else:
                problems.append(f"item {position}: parsed {got.item!r} vs JSON {want['item']!r}")
        if abs(got.amount - want["amount"]) > 0.01:
            problems.append(
                f"item {position} ({want['item']}): parsed {got.amount:,.2f} "
                f"vs JSON {want['amount']:,.2f}"
            )
    return problems, warnings


def load_bills() -> list[dict[str, Any]]:
    bills = [json.loads(path.read_text()) for path in sorted(BILLS_DIR.glob("*.json"))]
    if not bills:
        sys.exit(f"no bills in {BILLS_DIR}")
    return bills


def index_row(bill: dict[str, Any]) -> str:
    """One line of INDEX.md: everything the form needs besides the text."""
    schedule = bill.get("policy_schedule") or {}
    limit = schedule.get("room_limit_per_day")
    category = schedule.get("room_category")
    room = f"Rs {limit:,.0f}/day" if limit else (category or "-")
    return (
        f"| {bill['bill_id']} | {bill['policy']} | {bill['sum_insured']:,.0f} | "
        f"{bill['policy_start_date']} | {bill['admission_date']} | {room} | "
        f"{bill['category']} | {bill['total_charged']:,.0f} |"
    )


def write_index(bills: list[dict[str, Any]]) -> Path:
    header = [
        "# The 44 eval bills as pasteable text",
        "",
        "Generated by `eval/make_text_bills.py` - do not edit by hand.",
        "",
        "Paste the matching `.txt` into the bill box, then set the form to the",
        "values on that row. The sum insured is not cosmetic: on Star Health it",
        "picks the row of the room rent table, so the wrong figure gives the",
        "wrong limit and a confidently wrong deduction.",
        "",
        "`Room limit` is blank for most bills. Where it holds a figure, that is",
        "the policy schedule value - HDFC Ergo and Niva Bupa defer the room",
        "limit to the schedule and cannot be audited without it.",
        "",
        "| Bill | Policy | Sum insured | Policy start | Admission | Room limit | Category | Charged |",
        "| --- | --- | ---: | --- | --- | --- | --- | ---: |",
    ]
    body = [index_row(bill) for bill in bills]
    path = TEXT_DIR / "INDEX.md"
    path.write_text("\n".join(header + body) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="check with core.bill.parse_bill instead of the regex (44 model calls)",
    )
    args = parser.parse_args()

    bills = load_bills()
    check = compare_with_llm if args.llm else compare
    failures: dict[str, list[str]] = {}

    if not args.check:
        TEXT_DIR.mkdir(parents=True, exist_ok=True)

    notes: dict[str, list[str]] = {}
    for bill in bills:
        problems, warnings = check(bill)
        if problems:
            failures[bill["bill_id"]] = problems
        if warnings:
            notes[bill["bill_id"]] = warnings
        if not args.check:
            # Verbatim. Whatever the UI is handed has to be what was checked.
            (TEXT_DIR / f"{bill['bill_id']}.txt").write_text(bill["bill_text"].rstrip() + "\n")

    if not args.check:
        write_index(bills)
        print(f"wrote {len(bills)} bills and INDEX.md to {TEXT_DIR}")

    how = "core.bill.parse_bill" if args.llm else "the regex reader"
    if notes:
        print(f"\n{len(notes)} bills print a truncated description (amounts all agree):\n")
        for bill_id, warnings in notes.items():
            print(f"  {bill_id}")
            for warning in warnings:
                print(f"    - {warning}")
        print()
    if failures:
        print(f"\n{len(failures)} of {len(bills)} bills disagree with their text, per {how}:\n")
        for bill_id, problems in failures.items():
            print(f"  {bill_id}")
            for problem in problems:
                print(f"    - {problem}")
        return 1

    print(f"all {len(bills)} bills: the text and the JSON agree, per {how}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
