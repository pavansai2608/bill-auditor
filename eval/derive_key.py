"""How the answer key was first derived. IT NO LONGER REPRODUCES THE KEY ON DISK.

**Read this before running anything here.** `eval/answer_key.json` has been
changed since this script wrote it, by two recorded decisions that were applied
to the key and never back-ported into this file:

* **D-12, the citation rule** - a line the second pass rescales cites the clause
  defining associated medical expenses, not the room-rent cap that triggered it.
  85 lines: `II.1` -> `I.Def45` (47), `B.1.1` -> `A.1.2.Def5` (28),
  `B.1.1.1` -> `A.1.2.Def5` (10).
* **B03 and B31 became abstentions** - niva_bupa states no default room
  entitlement, so a shared-room line cannot be answered from the document.
  This script still answers both at 2,500.

So `--write` would silently revert 87 decisions. **It is refused.** The
divergence is pinned by `tests/test_derive_key_divergence.py` against a golden
file, so it cannot grow unnoticed; regenerate that file deliberately, after a
decision, and read the diff.

This file is kept as the record of where the key came from, and it is still the
honest answer to "how was this derived" for the 241 lines it does reproduce.

----

Every rule below was read off the PDF pages by hand and typed in as a constant -
`STAR_ROOM`, `STAR_CATARACT`, `AME_QUOTE` and the rest. **This script does not
open the PDFs.** It reads `eval/bills/*.json` and `data/non_payable.json`, and
nothing else. The clause id on a line comes from one of the dicts below, chosen
by a regex on the item text; the amount comes from arithmetic over those same
constants. Nothing here re-checks a constant against the document.

It imports no retriever, no judge and no audit code, which is real independence
of the *plumbing*: a bug in the splitter or the reranker cannot reach the key
and then be scored as a success. It is not independence of the *reading*. See
KNOWN_LIMITATIONS.md.

    uv run python eval/derive_key.py            # show what it would write
    uv run python eval/derive_key.py --write    # refused; see above

Where a policy genuinely does not decide a line, `allowed` is null and
`needs_human` is true. No number is invented to fill a gap.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BILLS = ROOT / "eval" / "bills"
KEY = ROOT / "eval" / "answer_key.json"
NON_PAYABLE = ROOT / "data" / "non_payable.json"

# --------------------------------------------------------------------------
# Rules, read off the PDFs. Page numbers are the printed PDF pages.
# --------------------------------------------------------------------------

# star_health p10, clause II.1. Above 4,00,000 the policy grants a room
# CATEGORY, not a rupee cap.
STAR_ROOM = {
    100000: 2000.0,
    200000: 2000.0,
    300000: 5000.0,
    400000: 5000.0,
    500000: None,
    1000000: None,
    1500000: None,
    2000000: None,
    2500000: None,
}
STAR_ROOM_CATEGORY = "Single Standard A/C Room"

# star_health p10, clause II.3 - cataract, (per eye, per policy period).
STAR_CATARACT = {
    100000: (12000.0, 12000.0),
    200000: (12000.0, 12000.0),
    300000: (25000.0, 35000.0),
    400000: (30000.0, 45000.0),
    500000: (40000.0, 60000.0),
    1000000: (50000.0, 75000.0),
    1500000: (50000.0, 75000.0),
    2000000: (50000.0, 75000.0),
    2500000: (50000.0, 75000.0),
}

# star_health p11, clause II.5 - modern treatments, per treatment per policy period.
STAR_ROBOTIC = {
    100000: 25000.0,
    200000: 50000.0,
    300000: 75000.0,
    400000: 200000.0,
    500000: 250000.0,
    1000000: 300000.0,
    1500000: 400000.0,
    2000000: 450000.0,
    2500000: 500000.0,
}

STAR_AMBULANCE_PER_STAY = 750.0  # p12, clause II.8

# Associated Medical Expenses - what a proportionate deduction reaches.
# star_health I.Def45 p8; hdfc_ergo A.1.2.Def5 p8; niva_bupa 6.2.4 p26.
AME_QUOTE = {
    "star_health": (
        'I.Def45 p8: "Associated Medical Expenses means expenses that shall include the '
        "applicable nursing charges, Operation theatre charges, Professional fees of Medical "
        "Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include "
        "cost of pharmacy and consumables, cost of implants and medical devices and cost of "
        'diagnostics, ICU charges"'
    ),
    "hdfc_ergo": (
        'A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on '
        "Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, "
        "oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and "
        "medical devices and Cost of diagnostics. Proportionate deduction shall not be "
        "applicable to 'ICU charges'\""
    ),
    "niva_bupa": (
        '6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, '
        "Medical Practitioners' fees and operation theatre charges\""
    ),
}

ROOM_CLAUSE = {"star_health": "II.1", "hdfc_ergo": "B.1.1", "niva_bupa": "6.2.4"}
PROPORTIONATE_CLAUSE = {"star_health": "II.1", "hdfc_ergo": "B.1.1.1", "niva_bupa": "6.2.4"}
WAITING_CLAUSE = {"star_health": "III.2", "hdfc_ergo": "C.1", "niva_bupa": "5.1.2"}
WAITING_MONTHS = 24

# Conditions on each policy's 24-month specified-disease list, read from
# star p29, hdfc p28, niva p15. All three lists carry these.
WAITING_ITEMS = r"cataract|hernia|knee replacement|joint replacement|hysterectomy|piles|fistula"

# --------------------------------------------------------------------------
# Line classification
# --------------------------------------------------------------------------

ROOM_RE = re.compile(r"room rent", re.I)
ICU_RE = re.compile(r"\bicu\b|intensive care|ventilator", re.I)
# Reached by proportionate deduction.
AME_RE = re.compile(
    r"surgeon fee|assistant surgeon|anaesthetist|nursing charges|"
    r"operation theatre|consultant visit",
    re.I,
)
# Explicitly outside AME in all three policies.
PHARMACY_RE = re.compile(r"medicines|drugs", re.I)
DIAGNOSTIC_RE = re.compile(
    r"investigation|x-ray|mri\b|ct\b|ultrasound|angiogram|"
    r"endoscopy|labs|blood panel|pre-operative",
    re.I,
)
IMPLANT_RE = re.compile(r"implant|lens|mesh", re.I)
AMBULANCE_RE = re.compile(r"ambulance", re.I)
ADMISSION_RE = re.compile(r"admission|registration", re.I)
CATARACT_RE = re.compile(r"cataract", re.I)
ROBOTIC_RE = re.compile(r"robotic|stem cell", re.I)
AYUSH_RE = re.compile(r"ayush", re.I)
PHYSIO_RE = re.compile(r"physiotherap", re.I)
RATE_RE = re.compile(r"([\d,]+)\s*x\s*(\d+)\s*day", re.I)

# Room categories in ascending order, so an occupied room can be compared with
# an entitlement expressed as a category rather than a rupee figure.
ROOM_RANK = [
    (re.compile(r"shared|sharing", re.I), 1),
    (re.compile(r"single standard a/?c|single a/?c", re.I), 2),
    (re.compile(r"single private", re.I), 3),
    (re.compile(r"deluxe", re.I), 4),
    (re.compile(r"suite", re.I), 5),
]
# star_health grants "Single Standard A/C Room" from 5,00,000 up.
STAR_CATEGORY_RANK = 2


def room_rank(item: str) -> int | None:
    for pattern, rank in ROOM_RANK:
        if pattern.search(item):
            return rank
    return None


def load_non_payable():
    raw = json.loads(NON_PAYABLE.read_text(encoding="utf-8"))
    if raw and isinstance(raw[0], str):
        return [{"no": i + 1, "item": n} for i, n in enumerate(raw)]
    return raw


def irdai_hit(item, entries):
    lowered = item.lower()
    best = None
    for entry in entries:
        name = re.split(r"[(/-]", entry["item"])[0].strip().lower()
        if len(name) > 3 and name in lowered and (best is None or len(name) > len(best["item"])):
            best = {"no": entry["no"], "item": name}
    return best


def months_between(start: str, end: str) -> int:
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def room_rate(item: str, line: dict) -> float | None:
    m = RATE_RE.search(item)
    if m:
        return float(m.group(1).replace(",", ""))
    return line["amount"] / line["qty"] if line["qty"] else None


def eligible_room(bill: dict) -> tuple[float | None, str, bool]:
    """(rupee limit per day, how it was derived, whether it is a category grant)."""
    policy, si = bill["policy"], bill["sum_insured"]
    schedule = bill.get("policy_schedule") or {}
    limit = schedule.get("room_limit_per_day")

    if limit is not None:
        return float(limit), f"policy schedule states room limit Rs {limit:,.0f} per day", False

    if policy == "star_health":
        capped = STAR_ROOM.get(si)
        if capped is not None:
            return (
                capped,
                (f"II.1 p10 table: Sum Insured {si:,} -> Up to {capped:,.0f}/- per day"),
                False,
            )
        return (
            None,
            (
                f'II.1 p10 table: Sum Insured {si:,} -> "{STAR_ROOM_CATEGORY}" - '
                "a room category, no rupee limit stated"
            ),
            True,
        )

    if policy == "hdfc_ergo":
        # The wording states a default, so a missing schedule is not a gap:
        # At Actuals is what the policy says applies.
        return (
            None,
            (
                "B.1.1 p11: \"Room rent limit shall be 'At Actuals' unless otherwise specified "
                'in the Policy Schedule"; no schedule supplied, so At Actuals applies'
            ),
            False,
        )
    return (
        None,
        (
            '6.2.4 p26: pro-rata applies to a room "higher than the eligible room category as '
            'specified in your Policy Schedule" - no schedule supplied and no default stated'
        ),
        True,
    )


def derive_bill(bill: dict, entries: list[dict]) -> list[dict]:
    policy, si = bill["policy"], bill["sum_insured"]
    out: list[dict] = []

    # --- bill-level: is the whole admission inside a waiting period? ---
    served = months_between(bill["policy_start_date"], bill["admission_date"])
    treatments = " | ".join(line["item"] for line in bill["lines"])
    waiting_hit = re.search(WAITING_ITEMS, treatments, re.I)
    in_waiting = bool(waiting_hit) and served < WAITING_MONTHS

    # --- bill-level: room rent and the proportionate ratio ---
    limit, limit_note, is_category = eligible_room(bill)
    room_line = next((ln for ln in bill["lines"] if ROOM_RE.search(ln["item"])), None)
    rate = room_rate(room_line["item"], room_line) if room_line else None

    ratio = 1.0
    ratio_note = ""
    room_unresolved = False
    if room_line and rate:
        if limit is not None and rate > limit:
            ratio = limit / rate
            ratio_note = (
                f"{PROPORTIONATE_CLAUSE[policy]}: room rent {rate:,.0f}/day exceeds the "
                f"eligible {limit:,.0f}/day, so associated medical expenses are reduced in "
                f"the same proportion: {limit:,.0f}/{rate:,.0f} = {ratio:.4f}"
            )
        elif is_category:
            # The entitlement is a category, not a figure. A room at or below
            # that category cannot breach it, so nothing is deducted. A room
            # above it does breach - but no rupee limit exists to build a ratio
            # from, so the line cannot be decided from the document.
            occupied = room_rank(room_line["item"])
            if policy == "star_health":
                room_unresolved = occupied is None or occupied > STAR_CATEGORY_RANK
                if not room_unresolved:
                    limit_note += (
                        f"; the room occupied ({room_line['item'].split('(')[-1].rstrip(') ')}) "
                        "is at or below that category, so nothing is deducted"
                    )
            else:
                # Niva Bupa states no default. Only the lowest category is safe.
                room_unresolved = occupied is None or occupied > 1
                if not room_unresolved:
                    limit_note += (
                        "; a shared room is the lowest category and cannot exceed any entitlement"
                    )

    for line in bill["lines"]:
        item, charged, qty = line["item"], line["amount"], line["qty"]
        entry = {
            "item": item,
            "charged": charged,
            "qty": qty,
            "allowed": None,
            "clause_id": None,
            "needs_human": None,
            "derivation": "",
        }

        if in_waiting:
            entry.update(
                allowed=0.0,
                clause_id=WAITING_CLAUSE[policy],
                needs_human=False,
                derivation=(
                    f'{WAITING_CLAUSE[policy]}: "Expenses related to the treatment of the '
                    f"listed conditions ... shall be excluded until the expiry of 24 months of "
                    f'continuous coverage"; policy began {bill["policy_start_date"]}, admitted '
                    f"{bill['admission_date']} = {served} months, and the treatment "
                    f"({waiting_hit.group(0)}) is on the list -> nil"
                ),
            )
            out.append(entry)
            continue

        hit = irdai_hit(item, entries)
        # "Ambulance" is on the IRDAI list but ambulance travel is a named
        # benefit, so the benefit clause wins.
        if hit and not AMBULANCE_RE.search(item):
            entry.update(
                allowed=0.0,
                clause_id="IRDAI-List-I",
                needs_human=False,
                derivation=f'IRDAI-List-I #{hit["no"]} "{hit["item"]}" is a non-payable item -> nil',
            )
            out.append(entry)
            continue

        if ADMISSION_RE.search(item) and policy == "star_health":
            entry.update(
                allowed=0.0,
                clause_id="III.31",
                needs_human=False,
                derivation='III.31 p32: "Hospital registration charges, admission charges, '
                "record charges, telephone charges and such other charges - Code "
                'Excl 34" -> nil',
            )
            out.append(entry)
            continue

        if AMBULANCE_RE.search(item) and policy == "star_health":
            allowed = min(charged, STAR_AMBULANCE_PER_STAY)
            entry.update(
                allowed=round(allowed, 2),
                clause_id="II.8",
                needs_human=False,
                derivation=f'II.8 p12: "road ambulance expenses up to Rs.750/- per '
                f'hospitalization"; min({charged:,.0f}, 750) = {allowed:,.0f}',
            )
            out.append(entry)
            continue

        if CATARACT_RE.search(item) and policy == "star_health":
            per_eye, _ = STAR_CATARACT[si]
            allowed = min(charged, per_eye)
            entry.update(
                allowed=round(allowed, 2),
                clause_id="II.3",
                needs_human=False,
                derivation=f"II.3 p10 table: Sum Insured {si:,} -> Up to {per_eye:,.0f}/- per "
                f"eye; min({charged:,.0f}, {per_eye:,.0f}) = {allowed:,.0f}",
            )
            out.append(entry)
            continue

        if ROBOTIC_RE.search(item) and policy == "star_health":
            cap = STAR_ROBOTIC[si]
            allowed = min(charged, cap)
            entry.update(
                allowed=round(allowed, 2),
                clause_id="II.5",
                needs_human=False,
                derivation=f"II.5 p11 table: Sum Insured {si:,} -> Up to {cap:,.0f}/- per "
                f"treatment per policy period; min({charged:,.0f}, {cap:,.0f}) = {allowed:,.0f}",
            )
            out.append(entry)
            continue

        if AYUSH_RE.search(item) and policy == "hdfc_ergo":
            entry.update(
                allowed=None,
                clause_id=None,
                needs_human=True,
                derivation='B.1.4 p12: AYUSH is payable "up to the Sub-limit specified against '
                'this Cover in the Policy Schedule" - the wording states no figure '
                "and no schedule was supplied",
            )
            out.append(entry)
            continue

        if ROOM_RE.search(item):
            if room_unresolved:
                entry.update(
                    allowed=None,
                    clause_id=ROOM_CLAUSE[policy],
                    needs_human=True,
                    derivation=f"{limit_note} - no rupee limit can be derived for this bill",
                )
            elif limit is not None:
                allowed = min(charged, limit * qty)
                entry.update(
                    allowed=round(allowed, 2),
                    clause_id=ROOM_CLAUSE[policy],
                    needs_human=False,
                    derivation=f"{limit_note}; {limit:,.0f} x {qty} = {limit * qty:,.0f}, "
                    f"min({charged:,.0f}, {limit * qty:,.0f}) = {allowed:,.0f}",
                )
            else:
                entry.update(
                    allowed=round(charged, 2),
                    clause_id=ROOM_CLAUSE[policy],
                    needs_human=False,
                    derivation=f"{limit_note}; charge is within entitlement -> paid in full",
                )
            out.append(entry)
            continue

        if ICU_RE.search(item):
            entry.update(
                allowed=round(charged, 2),
                clause_id=ROOM_CLAUSE[policy],
                needs_human=False,
                derivation=f"{AME_QUOTE[policy]}; ICU is outside associated medical expenses, "
                f"so no proportionate deduction -> paid in full",
            )
            out.append(entry)
            continue

        if AME_RE.search(item):
            if room_unresolved:
                entry.update(
                    allowed=None,
                    clause_id=PROPORTIONATE_CLAUSE[policy],
                    needs_human=True,
                    derivation=f"an associated medical expense, but {limit_note.lower()} - "
                    "whether a proportionate deduction applies cannot be determined",
                )
            elif ratio < 1.0:
                allowed = charged * ratio
                entry.update(
                    allowed=round(allowed, 2),
                    clause_id=PROPORTIONATE_CLAUSE[policy],
                    needs_human=False,
                    derivation=f"{ratio_note}; {AME_QUOTE[policy]}; "
                    f"{charged:,.0f} x {ratio:.4f} = {allowed:,.2f}",
                )
            else:
                entry.update(
                    allowed=round(charged, 2),
                    clause_id=ROOM_CLAUSE[policy],
                    needs_human=False,
                    derivation="room rent within the eligible limit, so no proportionate "
                    "deduction -> paid in full",
                )
            out.append(entry)
            continue

        if PHARMACY_RE.search(item) or DIAGNOSTIC_RE.search(item) or IMPLANT_RE.search(item):
            entry.update(
                allowed=round(charged, 2),
                clause_id=ROOM_CLAUSE[policy],
                needs_human=False,
                derivation=f"{AME_QUOTE[policy]}; pharmacy, consumables, implants and "
                f"diagnostics are outside associated medical expenses, so no "
                f"proportionate deduction -> paid in full",
            )
            out.append(entry)
            continue

        if PHYSIO_RE.search(item):
            entry.update(
                allowed=None,
                clause_id=None,
                needs_human=True,
                derivation="no clause in this policy states a limit for physiotherapy as a "
                "separate billed line",
            )
            out.append(entry)
            continue

        entry.update(
            allowed=round(charged, 2),
            clause_id=ROOM_CLAUSE[policy],
            needs_human=False,
            derivation="no specific limit found for this item; covered as a hospitalization "
            "expense -> paid in full",
        )
        out.append(entry)

    return out


REFUSAL = """--write is refused. This script no longer reproduces eval/answer_key.json.

Writing would revert 87 recorded decisions:
  85 citations set by D-12 (II.1 -> I.Def45, B.1.1 / B.1.1.1 -> A.1.2.Def5)
   2 abstentions on B03 and B31, which this script still answers at 2,500

Run without --write to see what it would produce, and
    uv run python tests/test_derive_key_divergence.py
to see exactly how the two disagree today."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true", help="refused; see the module docstring")
    args = parser.parse_args()

    if args.write:
        # Deliberately before any work: nothing about this run should look like
        # it was on its way to succeeding.
        print(REFUSAL, file=sys.stderr)
        return 2

    entries = load_non_payable()
    key = json.loads(KEY.read_text(encoding="utf-8"))
    bills = {
        p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(BILLS.glob("B*.json"))
    }

    filled = flagged = 0
    for bill_id, bill in bills.items():
        lines = derive_bill(bill, entries)
        target = key["bills"][bill_id]
        target["lines"] = lines
        answered = [ln for ln in lines if ln["allowed"] is not None]
        target["expected_total_allowed"] = (
            round(sum(ln["allowed"] for ln in answered), 2) if answered else None
        )
        filled += len(answered)
        flagged += sum(1 for ln in lines if ln["needs_human"])

    total = sum(len(v["lines"]) for v in key["bills"].values())
    print(f"lines: {total}   answered: {filled}   flagged needs_human: {flagged}")
    print("(dry run, and the only run there is - --write is refused, see the docstring)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
