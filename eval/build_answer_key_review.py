"""Lay out the evidence for a human to confirm or reject the answer key.

`eval/answer_key_provenance.md` says the key was written by a language model
reading the policy PDFs, that the judge in the pipeline is also a language model
reading the policy PDFs, and that until a person checks the least-confident
bills the accuracy numbers are provisional. This script prepares that check. It
does not perform it.

For every line of the bills named in that file it prints, side by side: the bill
line, what the key says is payable, the deduction, the clause the key cites, the
**verbatim** text of that clause taken from `data/clauses.json`, the page of the
source PDF that text was found on, and the arithmetic. Two empty columns follow
so the reader can sign each row off.

Three rules this file follows, because breaking any of them would make the
review worthless:

* **It never decides.** No entry is marked right or wrong. Where the evidence
  does not support an entry the row is listed under CANNOT SUPPORT with what is
  missing, for a person to settle.
* **It never edits the key.** `eval/answer_key.json` is opened read-only.
* **Quotes are lifted, never retyped.** Clause text comes out of the index
  verbatim. Where a quote cannot be located, the row says NOT FOUND rather than
  showing a reconstruction.

Page numbers are established by locating the text in the PDF, not by trusting
the `page` field: `extract_pages` is used so that star_health's two columns are
read in the same order the splitter reads them, because `extract_text()` on that
document interleaves the columns and finds nothing.

    uv run python eval/build_answer_key_review.py
    uv run python eval/build_answer_key_review.py --check   # verify, write nothing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.splitter import extract_pages

KEY_PATH = ROOT / "eval" / "answer_key.json"
BILLS_DIR = ROOT / "eval" / "bills"
CLAUSES_PATH = ROOT / "data" / "clauses.json"
NON_PAYABLE_PATH = ROOT / "data" / "non_payable.json"
POLICY_PDF = {
    "star_health": ROOT / "data" / "policies" / "star_health.pdf",
    "hdfc_ergo": ROOT / "data" / "policies" / "hdfc_ergo.pdf",
    "niva_bupa": ROOT / "data" / "policies" / "niva_bupa.pdf",
}
NON_PAYABLE_PDF = ROOT / "data" / "policies" / "non_payable_items.pdf"
OUT_PATH = ROOT / "eval" / "answer_key_review.md"

# The bills `answer_key_provenance.md` puts up for checking. Its prose says
# "ten"; its table names eight in the bill column (B38, B03/B31, B21/B39, B24,
# B41/B42) and four more inside the why column of the physiotherapy row (B04,
# B11, B19, B33). B43 is not in that table but has its own section saying the
# entry "needs your decision before the numbers mean anything", so it is here
# too. The count discrepancy is reported at the top of the output rather than
# resolved here - picking eight or twelve is exactly the kind of judgement this
# script must not make.
BILLS = ["B03", "B04", "B11", "B19", "B21", "B24", "B31", "B33", "B38", "B39", "B41", "B42", "B43"]
NAMED_IN_TABLE = {"B38", "B03", "B31", "B21", "B39", "B24", "B41", "B42"}
NAMED_IN_WHY = {"B04", "B11", "B19", "B33"}
NAMED_ELSEWHERE = {"B43"}

# The numbered judgement calls in answer_key_provenance.md. A row resting on one
# of these cannot be settled from the PDF alone, so it is marked and the call is
# named.
ASSUMPTIONS = {
    1: "co-payment is never applied (no bill states an age; Star Health II.28 needs entry age 61+)",
    2: "a waiting-period breach voids the entire admission, not only the surgery line",
    3: "ICU is never proportionately reduced (all three policies place it outside AME)",
    4: "medicines, diagnostics and implants are never proportionately reduced",
    5: "syringes are payable, gloves are not (gloves are IRDAI List I #56; syringes are not listed)",
    6: "an IRDAI 'Ambulance' list entry does not override a named ambulance benefit",
}
DIFFERENTIAL_BILLING = (
    "proportionate deduction applies - the policies disapply it at hospitals that "
    "do not follow differential billing, and nothing on a bill says whether this one does"
)


def norm(text: str) -> str:
    """Whitespace-folded, case-folded, and with the typographic quotes levelled.

    The PDFs use curly quotes and the key's derivations were retyped with
    straight ones, so a literal comparison reports a mismatch on wording that is
    in fact identical. Levelling them is the difference between finding a quote
    and calling it fabricated.
    """
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"\s+", " ", text).strip().lower()
    # The PDFs break long slash-joined runs with a space -
    # "surgeon/ anaesthetist/ physician/specialist" - and the key's derivations
    # were retyped without them. Left in, every quote of the Star Health
    # associated-medical-expenses definition reads as absent from the document,
    # which would put six correct citations per bill under CANNOT SUPPORT.
    return re.sub(r"\s*/\s*", "/", text)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def pdf_pages() -> dict[str, dict[int, str]]:
    """Every policy page, read the way the splitter reads it, normalised once."""
    pages: dict[str, dict[int, str]] = {}
    for policy, path in {**POLICY_PDF, "irdai": NON_PAYABLE_PDF}.items():
        if not path.exists():
            pages[policy] = {}
            continue
        pages[policy] = {page.page: norm(page.text or "") for page in extract_pages(path)}
    return pages


def find_pages(pages: dict[int, str], text: str, minimum: int = 12) -> list[int]:
    needle = norm(text)
    if len(needle) < minimum:
        return []
    return [number for number, body in pages.items() if needle in body]


def longest_supported_prefix(quote: str, haystack: str) -> int:
    """How many leading words of `quote` appear in `haystack`, by bisection.

    Used to say *where* a quote stops matching rather than only that it does,
    which is the difference between "retyped with different punctuation" and
    "this sentence is not in the document".
    """
    words = quote.split()
    low, high, best = 0, len(words), 0
    while low <= high:
        middle = (low + high) // 2
        if middle and norm(" ".join(words[:middle])) in haystack:
            best, low = middle, middle + 1
        else:
            high = middle - 1
    return best


QUOTED = re.compile(r'"([^"]{12,})"')
# The key saying, in its own words, that it located nothing. Harmless on a row
# that then abstains; on a row that is nevertheless paid in full it means the
# figure rests on no clause at all.
FOUND_NOTHING = re.compile(
    r"no specific limit found|no clause in this policy states|no benefit clause|"
    r"cannot be determined|no default stated|no rupee limit can be derived",
    re.I,
)
# "II.1 p10 table: ...", "I.Def45 p8: ...", "6.2.4 p26: ..." - the clause the
# derivation actually leans on, which is not always the clause_id on the row.
LEADING_REF = re.compile(r"^([A-Za-z0-9.]+(?:\.[A-Za-z0-9]+)*)\s+p(\d+)\b")


def derivation_quotes(derivation: str) -> list[str]:
    """The quoted spans, with any elision truncated at the ellipsis."""
    found = []
    for raw in QUOTED.findall(derivation or ""):
        span = raw.split("...")[0].split("…")[0].strip().rstrip(",;:")
        if len(span) >= 12:
            found.append(span)
    return found


def table_rows(clause: dict | None) -> list[str]:
    if clause is None:
        return []
    return [row for row in clause["text"].split("\n") if row.startswith("[table]")]


def cells(row: str) -> list[str]:
    return [cell.strip() for cell in row[len("[table]") :].split(" - ")]


RUPEE_ROW = re.compile(r"^\d[\d,]*/-$")


def damaged_table(clause: dict | None) -> str | None:
    """Whether a clause's table has header text sitting in its data cells.

    A merged or badly ruled grid can leave a column's *heading* forward-filled
    down its data rows. The row still looks like a table row, so nothing errors
    - but the columns no longer line up, and a figure read out of it may belong
    to a different treatment than the one above it. Star Health II.5 does this:
    its second grid carries "Vaporisation of the prostate ..." and "IONM-..."
    as the value of every data row.
    """
    rows = table_rows(clause)
    if not rows:
        return None
    heading_cells = set()
    for row in rows:
        parts = cells(row)
        if parts and not RUPEE_ROW.match(parts[0]):
            heading_cells.update(part for part in parts[1:] if len(part) > 12)
    damaged = []
    for row in rows:
        parts = cells(row)
        if parts and RUPEE_ROW.match(parts[0]):
            for position, part in enumerate(parts[1:], start=1):
                if part in heading_cells:
                    damaged.append((parts[0], position, part))
    if not damaged:
        return None
    where = ", ".join(f"{amount} column {position}" for amount, position, _ in damaged[:3])
    return (
        f"{len(damaged)} data cells in this clause's table hold column headings instead of "
        f"figures ({where}...), so the columns do not line up and a figure read out of the "
        "index may belong to a different treatment. Read the grid on the PDF page directly"
    )


def indian_figure(value: int) -> str:
    """1000000 -> "10,00,000" - the grouping the policy tables are printed in."""
    text = str(value)
    if len(text) <= 3:
        return text
    head, tail = text[:-3], text[-3:]
    head = re.sub(r"(?<=\d)(?=(\d\d)+$)", ",", head)
    return f"{head},{tail}"


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def operative_quote(clause: dict | None, line: dict, sum_insured: float) -> tuple[str, str]:
    """The clause text to show against a row, chosen mechanically.

    In order: the sentence the key's own derivation quoted, since that is what
    the key leaned on; else the `[table]` row for this bill's sum insured, for
    the table-driven clauses; else the clause's opening sentence. Never a
    summary, never a stitched-together phrase.
    """
    if clause is None:
        return "NOT FOUND", "no clause body to quote"

    body = clause["text"]
    for quote in derivation_quotes(line.get("derivation", "")):
        for sentence in sentences(body):
            if norm(quote)[:60] in norm(sentence):
                return sentence, "the sentence the key's derivation quotes"
        if norm(quote) in norm(body):
            return quote, "found in the clause body, mid-sentence"

    indian = indian_figure(int(sum_insured))
    rows = table_rows(clause)
    if rows:
        # Every heading, and every data row for this bill's sum insured - not
        # the first match. A clause can hold more than one grid (Star Health
        # II.5 holds two, six treatments each), and showing one row of one grid
        # hides the question of which column a figure came out of, which is
        # the doubt the provenance file raises about this very clause.
        headings = [row for row in rows if not RUPEE_ROW.match(cells(row)[0])]
        matching = [row for row in rows if cells(row)[0].startswith(indian)]
        if matching:
            return (
                "\n".join(headings + matching),
                f"every heading in this clause's table(s), and every data row for "
                f"sum insured {indian} - read the columns across",
            )

    # A clause body often opens on its own heading ("Claims\na."), which quotes
    # nothing useful, so the fallback takes the first sentence with enough in it
    # to be checkable against the page.
    for sentence in sentences(body):
        if len(sentence) >= 40:
            return sentence, "the clause's first full sentence (its derivation quotes nothing)"
    return "NOT FOUND", "no sentence in this clause is long enough to quote"


def money(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f}"


def arithmetic(line: dict) -> str:
    """The key's own derivation, which is where its arithmetic is written."""
    text = (line.get("derivation") or "").strip()
    return text or "NOT FOUND - the key records no derivation for this line"


def assumption_flags(line: dict, entry: dict, clause: dict | None) -> list[str]:
    """Which judgement calls a row rests on, so it is not read as clause-settled."""
    item = line["item"].lower()
    derivation = (line.get("derivation") or "").lower()
    flags = []
    if "proportion" in derivation and "no proportionate deduction" not in derivation:
        flags.append(f"ASSUMPTION (differential billing): {DIFFERENTIAL_BILLING}")
    if "icu" in item and "outside associated medical expenses" in derivation:
        flags.append(f"ASSUMPTION 3: {ASSUMPTIONS[3]}")
    consumable = any(w in item for w in ("medicine", "drug", "investigation", "lens", "implant"))
    if consumable and "outside associated medical expenses" in derivation:
        flags.append(f"ASSUMPTION 4: {ASSUMPTIONS[4]}")
    if "syringe" in item:
        flags.append(f"ASSUMPTION 5: {ASSUMPTIONS[5]}")
    if "ambulance" in item:
        flags.append(f"ASSUMPTION 6: {ASSUMPTIONS[6]}")
    if entry.get("category") == "waiting_period":
        flags.append(f"ASSUMPTION 2: {ASSUMPTIONS[2]}")
    no_schedule = entry.get("policy_schedule") is None and clause is not None
    if no_schedule and "policy schedule" in clause["text"].lower():
        flags.append(
            "ASSUMPTION (absent policy schedule): the clause defers the limit to a "
            "schedule that this bill does not supply"
        )
    return flags


def review_line(
    line: dict,
    entry: dict,
    clauses: dict,
    non_payable: dict[int, str],
    pages: dict[str, dict[int, str]],
) -> dict:
    """Everything needed to check one row, plus every way it failed to check."""
    policy = entry["policy"]
    clause_id = line.get("clause_id")
    clause = clauses.get((clause_id, policy)) if clause_id else None
    problems: list[str] = []
    notes: list[str] = []

    charged = line["charged"]
    allowed = line.get("allowed")
    flagged = bool(line.get("needs_human"))
    deduction = None if (flagged or allowed is None) else charged - allowed

    derivation = line.get("derivation") or ""
    reference = LEADING_REF.match(derivation.strip())
    leaned_on = reference.group(1) if reference else None
    claimed_page = int(reference.group(2)) if reference else None

    if clause_id == "IRDAI-List-I":
        number = re.search(r"#(\d+)", derivation)
        listed = non_payable.get(int(number.group(1))) if number else None
        if listed is None:
            problems.append(
                f"cites IRDAI-List-I but item #{number.group(1) if number else '?'} "
                "is not in data/non_payable.json"
            )
            quote, basis = "NOT FOUND", "no matching list entry"
            found_on = []
        else:
            quote = f"IRDAI List I, item {number.group(1)}: {listed}"
            basis = "data/non_payable.json, the IRDAI non-payable list"
            # These entries are short ("Gloves"), so the usual length guard has
            # to come off, and they are looked for in the IRDAI list document
            # first and in the policy's own annexure second.
            in_list = find_pages(pages.get("irdai", {}), listed[:40], minimum=4)
            in_policy = find_pages(pages.get(policy, {}), listed[:40], minimum=4)
            found_on = in_list or in_policy
            if in_list and in_policy:
                basis += (
                    f" - non_payable_items.pdf p{in_list[0]}, and reproduced in "
                    f"{policy}.pdf p{in_policy[0]}"
                )
            elif in_policy:
                basis += f" - found in {policy}.pdf p{in_policy[0]}"
            elif not in_list:
                problems.append(
                    f"item #{number.group(1)} {listed[:40]!r} was not located in "
                    "non_payable_items.pdf or in the policy wording"
                )
    elif clause_id and clause is None:
        problems.append(f"cites {clause_id!r}, which is not in data/clauses.json for {policy}")
        quote, basis, found_on = "NOT FOUND", "clause id not in the index", []
    else:
        # Show the text the key actually reasoned from. Where the derivation
        # opens "I.Def45 p8: ...", that definition is the evidence even though
        # the row cites II.1 - quoting II.1 here would hide the mismatch rather
        # than expose it. The mismatch itself is flagged separately below.
        evidence = clauses.get((leaned_on, policy)) if leaned_on else None
        source = evidence or clause
        quote, basis = operative_quote(source, line, entry["sum_insured"])
        if evidence is not None and evidence is not clause:
            basis = f"{basis}, from {leaned_on} — the clause the derivation reasons from"
        is_table_block = "\n" in quote
        if is_table_block:
            # A block of table rows never appears contiguously in the page text
            # - the rows are reassembled from cell geometry. Locate the grid by
            # its first heading instead, and do not run the divergence check on
            # something that was never a running sentence.
            heading = quote.split("\n")[0][len("[table] ") :].split(" - ")[0]
            longest = max(quote.split("\n"), key=len)
            found_on = find_pages(
                pages.get(policy, {}), longest[len("[table] ") :][:60]
            ) or find_pages(pages.get(policy, {}), heading)
        else:
            found_on = find_pages(pages.get(policy, {}), quote) if quote != "NOT FOUND" else []
        if quote != "NOT FOUND" and not found_on and not is_table_block:
            if len(norm(quote)) < 12:
                # A limit of this script, not a defect in the key - it goes in
                # the row as a note so it does not inflate CANNOT SUPPORT.
                notes.append(
                    "no operative sentence could be selected automatically; read the "
                    "clause whole in the appendix"
                )
            else:
                supported = longest_supported_prefix(
                    quote, " || ".join(pages.get(policy, {}).values())
                )
                total = len(quote.split())
                problems.append(
                    f"the quoted text was not located in {policy}.pdf; the first "
                    f"{supported} of {total} words match, then it diverges"
                )
        damage = damaged_table(source)
        if damage and "[table]" in quote:
            problems.append(damage)

    # A quote the derivation makes that the cited clause does not contain.
    for spoken in derivation_quotes(derivation):
        if clause is not None and norm(spoken) not in norm(clause["text"]):
            elsewhere = [
                cid
                for (cid, pol), body in clauses.items()
                if pol == policy and norm(spoken) in norm(body["text"])
            ]
            where = (
                f"it is in {elsewhere[:3]}" if elsewhere else "it is in no clause of this policy"
            )
            problems.append(
                f"the derivation quotes text that clause {clause_id} does not contain - {where}"
            )

    mismatch = leaned_on and clause_id and leaned_on not in (clause_id, "room")
    if mismatch and (leaned_on, policy) in clauses:
        problems.append(
            f"clause_id is {clause_id} but the derivation reasons from {leaned_on}; "
            "citation accuracy is scored on clause_id"
        )

    if claimed_page is not None and found_on and claimed_page not in found_on:
        problems.append(
            f"the derivation says p{claimed_page}; the quoted text is on "
            f"{'/'.join(f'p{p}' for p in found_on)}"
        )

    if not flagged and deduction is not None and deduction > 0 and not clause_id:
        problems.append("a deduction is applied with no clause_id at all")

    # The key saying it found nothing, on a row it nevertheless settled.
    if not flagged and FOUND_NOTHING.search(derivation):
        problems.append(
            "the derivation itself says no clause was located, yet the row is answered "
            f"rather than flagged: {FOUND_NOTHING.search(derivation).group(0)!r}"
        )

    coverage_prompt = None
    if not flagged and deduction == 0:
        coverage_prompt = (
            f"Paid in full. The only clause cited is `{clause_id}`. Confirm it establishes "
            "that this item is **covered**, and not merely that no limit reduces it - "
            '"no deduction" is a claim that needs a citation of its own.'
        )

    return {
        "item": line["item"],
        "charged": charged,
        "allowed": allowed,
        "flagged": flagged,
        "deduction": deduction,
        "clause_id": clause_id,
        "quote": quote,
        "basis": basis,
        "pages": found_on,
        "recorded_page": clause["page"] if clause else None,
        "arithmetic": arithmetic(line),
        "assumptions": assumption_flags(line, entry, clause),
        "problems": problems,
        "notes": notes,
        "coverage_prompt": coverage_prompt,
    }


def bill_text_row(bill: dict, item: str) -> str:
    """The line as the printed bill shows it, when it can be matched."""
    for raw in bill.get("bill_text", "").splitlines():
        if item.lower()[:22] in raw.lower():
            return raw.strip()
    return item


def render(reviews: dict[str, dict], counts: dict[str, int]) -> str:
    out: list[str] = []
    w = out.append

    w("# Answer key review — evidence for a human check")
    w("")
    w("`eval/answer_key_provenance.md` records that this key was written by a language")
    w("model reading the policy PDFs, that the judge in the pipeline is also a language")
    w("model reading the policy PDFs, and that **until a person checks the")
    w("least-confident bills the accuracy numbers are provisional**. This file is that")
    w("check laid out, not that check performed.")
    w("")
    w("**Nothing here decides whether an entry is right.** Every row carries the bill")
    w("line, what the key claims, the clause it cites quoted verbatim from")
    w("`data/clauses.json`, the page of the source PDF that text was located on, and")
    w("the arithmetic — then two empty columns for you. Rows the evidence does not")
    w("support are listed under **CANNOT SUPPORT** below rather than corrected.")
    w("")
    w(f"**{counts['rows']} rows across {counts['bills']} bills.** Sign off in the")
    w("CONFIRMED column: `y` if the PDF bears the entry out, `n` if it does not.")
    w("")
    w("## Which bills these are")
    w("")
    w('`answer_key_provenance.md` says "the ten bills listed at the end", but the table')
    w("at its end names **eight** in the bill column (B38, B03, B31, B21, B39, B24, B41,")
    w("B42) and **four more** inside the why column of its physiotherapy row (B04, B11,")
    w('B19, B33). B43 is not in that table at all but has its own section ending "this')
    w('needs your decision before the numbers mean anything".')
    w("")
    w("Eight, twelve or thirteen is your call to make, not this script's, so **all")
    w("thirteen are here** — a superset cannot be wrong by omission. Where a bill sits:")
    w("")
    w("| Bill | Why it is in scope |")
    w("|---|---|")
    for bill_id in BILLS:
        if bill_id in NAMED_IN_TABLE:
            why = "named in the bill column of *Entries I am least confident in*"
        elif bill_id in NAMED_IN_WHY:
            why = "named in the why column of the physiotherapy row"
        else:
            why = "*Where the key contradicts the bills' own design* — B43 needs a decision"
        w(f"| {bill_id} | {why} |")
    w("")

    # CANNOT SUPPORT, first, as asked.
    w("## CANNOT SUPPORT")
    w("")
    w("Entries whose cited clause does not exist, does not contain what the key says it")
    w("does, or does not establish what the key concludes from it. **Not corrected, not")
    w("adjusted — reported.** Each is a question for you, not a verdict from me.")
    w("")
    total_problems = 0
    for bill_id in BILLS:
        rows = [r for r in reviews[bill_id]["rows"] if r["problems"]]
        if not rows:
            continue
        w(f"### {bill_id} ({reviews[bill_id]['policy']})")
        w("")
        for row in rows:
            total_problems += 1
            w(f"- **{row['item']}** — cites `{row['clause_id']}`")
            for problem in row["problems"]:
                w(f"  - {problem}")
        w("")
    if total_problems == 0:
        w("*(none)*")
        w("")
    w(f"**{total_problems} rows flagged.**")
    w("")

    for bill_id in BILLS:
        review = reviews[bill_id]
        w(f"## {bill_id}")
        w("")
        w("| | |")
        w("|---|---|")
        w(f"| Policy | {review['policy']} |")
        w(f"| Sum insured | Rs {review['sum_insured']:,.0f} |")
        w(f"| Policy start date | {review['policy_start_date']} |")
        w(f"| Admission date | {review['admission_date']} |")
        w(f"| Policy schedule | {review['schedule']} |")
        w(f"| Category | {review['category']} |")
        w(f"| Total charged | Rs {review['total_charged']:,.0f} |")
        w(f"| Key total payable | Rs {review['expected']:,.0f} |")
        w("")

        for number, row in enumerate(review["rows"], start=1):
            w(f"### {bill_id}.{number} — {row['item']}")
            w("")
            w("| Field | Value |")
            w("|---|---|")
            w(f"| Bill line, as printed | `{row['printed']}` |")
            payable = (
                "**flagged `needs_human`**" if row["flagged"] else f"Rs {money(row['allowed'])}"
            )
            w(f"| Key says payable | {payable} |")
            w(
                f"| Deduction | {'-' if row['deduction'] is None else 'Rs ' + money(row['deduction'])} |"
            )
            w(f"| clause_id | `{row['clause_id']}` |")
            page = "/".join(f"p{p}" for p in row["pages"]) if row["pages"] else "**NOT FOUND**"
            recorded = f" (index records p{row['recorded_page']})" if row["recorded_page"] else ""
            w(f"| Located in the PDF on | {page}{recorded} |")
            w(f"| Why this text | {row['basis']} |")
            w("")
            source_file = (
                "`data/non_payable.json`"
                if str(row["clause_id"]) == "IRDAI-List-I"
                else "`data/clauses.json`"
            )
            w(f"Clause text, verbatim from {source_file}:")
            w("")
            w("```")
            w(row["quote"])
            w("```")
            w("")
            w("Arithmetic, as the key records it:")
            w("")
            w("```")
            w(row["arithmetic"])
            w("```")
            w("")
            for flag in row["assumptions"]:
                w(f"> **{flag}**")
                w(">")
                w("> This row cannot be settled from the PDF alone.")
                w("")
            for note in row["notes"]:
                w(f"> *Note: {note}*")
                w("")
            if row["coverage_prompt"]:
                w(f"> **Coverage check.** {row['coverage_prompt']}")
                w("")
            for problem in row["problems"]:
                w(f"> **CANNOT SUPPORT:** {problem}")
                w("")
            w("| CONFIRMED | NOTES |")
            w("|---|---|")
            w("|  |  |")
            w("")

    w("## Appendix — the clauses in full")
    w("")
    w("Every distinct clause cited above, quoted whole from `data/clauses.json`, so a")
    w("row's short quote can be read in its context.")
    w("")
    for (clause_id, policy), clause in sorted(counts["clauses_used"].items()):
        w(f"### {clause_id} — {policy}")
        w("")
        w(f"*{clause['title']}* · index records page {clause['page']}")
        w("")
        w("```")
        w(clause["text"])
        w("```")
        w("")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = parser.parse_args()

    key = load_json(KEY_PATH)["bills"]
    clauses = {(c["clause_id"], c["policy"]): c for c in load_json(CLAUSES_PATH)}
    non_payable = {entry["no"]: entry["item"] for entry in load_json(NON_PAYABLE_PATH)}
    pages = pdf_pages()
    missing_pdfs = [policy for policy, page_map in pages.items() if not page_map]
    if missing_pdfs:
        print(f"warning: no text read for {missing_pdfs} - pages will show NOT FOUND")

    reviews: dict[str, dict] = {}
    rows_total = 0
    clauses_used: dict[tuple[str, str], dict] = {}

    for bill_id in BILLS:
        entry = key[bill_id]
        bill = load_json(BILLS_DIR / f"{bill_id}.json")
        schedule = entry.get("policy_schedule")
        rows = []
        for line in entry["lines"]:
            row = review_line(line, entry, clauses, non_payable, pages)
            row["printed"] = bill_text_row(bill, line["item"])
            rows.append(row)
            rows_total += 1
            found = clauses.get((line.get("clause_id"), entry["policy"]))
            if found:
                clauses_used[(line["clause_id"], entry["policy"])] = found
        reviews[bill_id] = {
            "policy": entry["policy"],
            "sum_insured": entry["sum_insured"],
            "policy_start_date": entry.get("policy_start_date", "-"),
            "admission_date": entry.get("admission_date", "-"),
            "schedule": json.dumps(schedule) if schedule else "none supplied",
            "category": entry.get("category", "-"),
            "total_charged": entry["total_charged"],
            "expected": entry["expected_total_allowed"],
            "rows": rows,
        }

    counts = {"rows": rows_total, "bills": len(BILLS), "clauses_used": clauses_used}
    text = render(reviews, counts)
    flagged = sum(1 for r in reviews.values() for row in r["rows"] if row["problems"])

    if args.check:
        print(f"{rows_total} rows across {len(BILLS)} bills; {flagged} rows flagged CANNOT SUPPORT")
        return 0

    OUT_PATH.write_text(text)
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"{rows_total} rows across {len(BILLS)} bills")
    print(f"{flagged} rows flagged CANNOT SUPPORT")
    print(f"{len(clauses_used)} distinct clauses quoted in full in the appendix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
