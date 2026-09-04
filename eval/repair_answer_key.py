"""Point every answer-key entry at the clause its own derivation quotes.

The key was written by reading the PDFs, and 37 of the 93 entries that were
reviewed by hand cite a clause that does not contain the text the derivation
puts in quotation marks. The quote is the evidence; the clause id is a label
someone typed next to it. Where the two disagree, the quote is the one that can
be checked, so it decides.

**The rule, and it is the whole rule:**

    Take the text the derivation quotes. Search every clause of that bill's
    policy for it. Exactly one clause contains it -> that is the clause id.
    Zero clauses, or more than one -> change nothing, and print it for a human
    to settle against the PDF.

Nothing about the system under test is consulted. This script imports no
retriever, no judge and no audit code, and it never reads a verdict, a report
or a checkpoint - the same firewall `derive_key.py` keeps, for the same reason:
a key repaired to agree with the output would measure agreement rather than
correctness. It also never touches `allowed`, `needs_human` or any amount. A
citation is not evidence about a figure.

    uv run python eval/repair_answer_key.py            # report, change nothing
    uv run python eval/repair_answer_key.py --apply    # write the fixes

`--apply` rewrites `eval/answer_key.json` in place and appends a record of
every change - old id, new id, matched text - to `eval/answer_key_review.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from build_answer_key_review import derivation_quotes, longest_supported_prefix, norm

KEY_PATH = ROOT / "eval" / "answer_key.json"
CLAUSES_PATH = ROOT / "data" / "clauses.json"
REVIEW_PATH = ROOT / "eval" / "answer_key_review.md"
TODO_PATH = ROOT / "eval" / "answer_key_todo.md"

# Cited by the non-payable fast path and by the key, sourced from
# data/non_payable.json rather than from a clause. Nothing to search for.
IRDAI = "IRDAI-List-I"

# A quote this short matches half the document. The review file uses the same
# floor, for the same reason.
MIN_QUOTE = 12


def clauses_by_policy() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for clause in json.loads(CLAUSES_PATH.read_text()):
        grouped.setdefault(clause["policy"], []).append(clause)
    return grouped


def containing(quote: str, clauses: list[dict]) -> list[str]:
    """Every clause of this policy whose text contains `quote`, normalised."""
    needle = norm(quote)
    if len(needle) < MIN_QUOTE:
        return []
    return sorted({c["clause_id"] for c in clauses if needle in norm(c["text"])})


class Finding:
    """One line's verdict: unchanged, fixed, or handed back to a person."""

    def __init__(self, bill: str, index: int, item: str, cited: str) -> None:
        self.bill = bill
        self.index = index
        self.item = item
        self.cited = cited
        self.new: str | None = None
        self.quote = ""
        self.why = ""
        self.derivation = ""
        self.quotes: list[str] = []
        self.candidates: list[str] = []  # clauses of this policy containing a quote
        self.elsewhere: list[str] = []  # "policy:clause" in ANOTHER policy - a red flag
        self.leading_ref = ""  # the clause the derivation names in its own text
        self.leading_page = 0
        self.charged = 0.0
        self.page = 0  # the page of the clause currently cited
        self.policy = ""
        self.prefix: tuple[int, int] | None = None  # (words matched, words quoted)
        self.stops_at = ""

    @property
    def where(self) -> str:
        return f"{self.bill} line {self.index + 1}"


# "II.1 p10 table: ...", "I.Def45 p8: ..." - the clause the derivation leans on,
# written into its own text. Where it disagrees with the clause_id on the row,
# the row is worth a person's time even though there is no quote to search for.
LEADING_REF = re.compile(r"^([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)\s+p(\d+)\b")


def examine(bill: str, index: int, line: dict, clauses: list[dict]) -> Finding | None:
    """Compare the cited clause with the clause the derivation quotes."""
    cited = line.get("clause_id")
    finding = Finding(bill, index, line["item"], cited or "")

    if not cited:
        return None  # an abstention cites nothing; there is nothing to repair
    if cited == IRDAI:
        return None  # sourced from non_payable.json, not from a clause

    derivation = line.get("derivation", "") or ""
    finding.derivation = derivation
    reference = LEADING_REF.match(derivation.strip())
    if reference:
        finding.leading_ref = reference.group(1)
        finding.leading_page = int(reference.group(2))

    quotes = [q for q in derivation_quotes(derivation) if len(norm(q)) >= MIN_QUOTE]
    finding.quotes = quotes
    if not quotes:
        # Table derivations ("II.1 p10 table: Sum Insured 300,000 -> ...") carry
        # no quotation marks. There is no quoted text, so there is no evidence
        # here to move the citation with.
        finding.why = "no quoted text in the derivation"
        return finding

    # Every quote must agree, and agree on one clause. A derivation that quotes
    # two clauses is describing a chain of reasoning, and which link the
    # citation belongs to is a judgement, not a search.
    matches: list[set[str]] = [set(containing(q, clauses)) for q in quotes]
    agreed = set.intersection(*matches) if matches else set()
    finding.candidates = sorted(set().union(*matches)) if matches else []

    if cited in agreed:
        finding.why = "the cited clause contains every quote"
        return finding

    if len(agreed) == 1:
        finding.new = next(iter(agreed))
        finding.quote = max(quotes, key=len)
        finding.why = "one clause contains every quote"
        return finding

    if not agreed:
        # How far the quote gets inside the clause the row cites, before it
        # stops matching. "0 of 9 words" is a broken clause; "7 of 9" is a
        # derivation that paraphrased instead of copying, and the two need
        # completely different things done about them.
        cited_clause = next((c for c in clauses if c["clause_id"] == cited), None)
        if cited_clause is not None:
            longest = max(quotes, key=len)
            words = longest.split()
            matched = longest_supported_prefix(longest, norm(cited_clause["text"]))
            finding.prefix = (matched, len(words))
            finding.stops_at = " ".join(words[matched : matched + 6])
        found = sorted(set().union(*matches)) if matches else []
        finding.why = (
            f"no clause contains every quote (per-quote matches: {[sorted(m) for m in matches]})"
            if found
            else "the quoted text is in no clause of this policy"
        )
    else:
        finding.why = f"{len(agreed)} clauses contain every quote: {sorted(agreed)}"
    return finding


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the fixes")
    args = parser.parse_args()

    key = json.loads(KEY_PATH.read_text())
    grouped = clauses_by_policy()

    unchanged: list[Finding] = []
    fixable: list[Finding] = []
    unresolved: list[Finding] = []
    skipped = 0

    all_clauses = [c for group in grouped.values() for c in group]
    pages = {(c["policy"], c["clause_id"]): c["page"] for c in all_clauses}

    for bill in sorted(key["bills"]):
        entry = key["bills"][bill]
        policy = entry["policy"]
        clauses = grouped.get(policy, [])
        for index, line in enumerate(entry["lines"]):
            finding = examine(bill, index, line, clauses)
            if finding is not None:
                finding.policy = policy
                finding.charged = line.get("charged") or 0.0
                finding.page = pages.get((policy, finding.cited), 0)
                # A quote that is nowhere in this policy but sits in another one
                # is the loudest signal on the list: either the wrong insurer's
                # wording was read, or this policy's extraction is damaged.
                if finding.quotes and not finding.candidates:
                    found = set()
                    for quote in finding.quotes:
                        for clause in all_clauses:
                            if clause["policy"] != policy and norm(quote) in norm(clause["text"]):
                                found.add(f"{clause['policy']}:{clause['clause_id']}")
                    finding.elsewhere = sorted(found)
            if finding is None:
                skipped += 1
            elif finding.new:
                fixable.append(finding)
            elif finding.why == "the cited clause contains every quote":
                unchanged.append(finding)
            else:
                unresolved.append(finding)

    total = len(unchanged) + len(fixable) + len(unresolved)
    print(f"{total} cited lines examined ({skipped} cite nothing, or cite {IRDAI})")
    print(f"  {len(unchanged):3d} already point at the clause they quote")
    print(f"  {len(fixable):3d} point at the wrong clause, and exactly one clause matches")
    print(f"  {len(unresolved):3d} cannot be settled from the text - listed below")

    print("\n--- WOULD FIX ---")
    for f in sorted(fixable, key=lambda f: (f.bill, f.index)):
        print(f"  {f.where:14s} {f.item[:38]:40s} {f.cited:12s} -> {f.new}")

    print("\n--- CANNOT SETTLE (read the PDF yourself) ---")
    for f in sorted(unresolved, key=lambda f: (f.bill, f.index)):
        print(f"  {f.where:14s} {f.item[:38]:40s} cites {f.cited:12s} {f.why}")

    if not args.apply:
        print("\nNothing written. Re-run with --apply to write the fixes.")
        return 0

    for f in fixable:
        key["bills"][f.bill]["lines"][f.index]["clause_id"] = f.new
    KEY_PATH.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(fixable)} citation fixes to {KEY_PATH.relative_to(ROOT)}")

    REVIEW_PATH.write_text(REVIEW_PATH.read_text() + record(fixable, unresolved))
    print(f"appended the record to {REVIEW_PATH.relative_to(ROOT)}")

    TODO_PATH.write_text(todo(unresolved))
    print(f"wrote the shortlist to {TODO_PATH.relative_to(ROOT)}")
    return 0


def group_key(f: Finding) -> tuple:
    """Rows that are one question, not several.

    Thirteen rows citing `star_health III.2` with the same quote are a single
    thing to check: is III.2 the specified-disease waiting period? Sorting by
    row count rather than by row puts the questions that settle the most lines
    at the top, which is the only ordering that respects the reader's time.
    """
    return (f.policy, f.cited, f.why.split("(")[0].strip())


def tier(f: Finding) -> int:
    """1 is worth reading the PDF for; 3 is a formality."""
    if f.elsewhere:
        return 1  # the quote is in a different policy's wording
    if f.quotes and not f.candidates:
        return 1  # the quote is nowhere at all
    if f.quotes:
        return 2  # the quote is somewhere, but not where the row points
    if f.leading_ref and f.leading_ref != f.cited:
        return 2  # the derivation names one clause and the row cites another
    return 3  # a table derivation, no quoted text to check


TIER_NAMES = {
    1: "The evidence and the citation disagree",
    2: "The evidence is incomplete",
    3: "There is no quoted text to check",
}

TIER_NOTES = {
    1: (
        "The derivation quotes text that is **not in the clause the row cites**, and in "
        "some cases not in that policy at all. Either the wrong clause is cited, the "
        "quote was paraphrased rather than copied, or the clause index has damaged that "
        "clause's text. All three need the PDF."
    ),
    2: (
        "The quoted text was located, but not in the cited clause, or the derivation "
        "names one clause in its own opening and the row cites another."
    ),
    3: (
        "A table derivation - `II.1 p10 table: Sum Insured 300,000 -> Up to 5,000/- per "
        "day` - carries no quotation marks, so there is no span to search for. The "
        "citation may be perfectly correct; this method simply cannot confirm it. The "
        "table renderings themselves are pinned by `tests/test_tables_golden.py`, which "
        "is the stronger check on this group, so read these only after the tiers above."
    ),
}


def todo(unresolved: list[Finding]) -> str:
    """The shortlist a person has to settle against the PDFs, worst first."""
    groups: dict[tuple, list[Finding]] = {}
    for f in unresolved:
        groups.setdefault(group_key(f), []).append(f)

    ordered = sorted(groups.values(), key=lambda rows: (tier(rows[0]), -len(rows)))

    out = [
        "# Answer key — what still needs a human and a PDF",
        "",
        "Written by `eval/repair_answer_key.py`. Every row here is a citation that",
        "**could not be settled from the text**: the clause the derivation quotes is not",
        "the clause the row cites, or there is no quoted text to search for at all.",
        "",
        "The mechanical repair changed nothing, because there was nothing it could change",
        "safely - see the citation-repair section of `answer_key_review.md`. What is left",
        "is what a person has to read the document for.",
        "",
        "**Rows are grouped into questions.** Thirteen rows citing the same clause with the",
        "same quote are one question, not thirteen, and settling it settles all of them.",
        "The groups are ordered by how much they decide.",
        "",
        f"**{len(unresolved)} rows, {len(ordered)} questions.**",
        "",
    ]

    counts: dict[int, int] = {}
    for rows in ordered:
        counts[tier(rows[0])] = counts.get(tier(rows[0]), 0) + len(rows)
    out += ["| tier | what it means | rows |", "|---|---|---|"]
    for level in sorted(counts):
        out.append(f"| {level} | {TIER_NAMES[level]} | {counts[level]} |")
    out.append("")

    current = 0
    for number, rows in enumerate(ordered, start=1):
        head = rows[0]
        if tier(head) != current:
            current = tier(head)
            out += ["", f"## Tier {current} — {TIER_NAMES[current]}", "", TIER_NOTES[current], ""]

        quote = re.sub(r"\s+", " ", head.quotes[0]) if head.quotes else "(none)"
        page = head.page or head.leading_page
        out += [
            f"### Q{number}. `{head.policy}` `{head.cited}` — {len(rows)} row"
            + ("s" if len(rows) != 1 else ""),
            "",
            f"- **Open** {head.policy}.pdf at **page {page or '?'}** "
            f"(where `{head.cited}` was split from)",
            f"- **The row quotes** “{quote[:170]}”",
        ]
        if head.candidates:
            out.append(
                "- **Clauses of this policy that do contain it** "
                + ", ".join(f"`{c}`" for c in head.candidates)
            )
        elif head.quotes:
            out.append("- **No clause of this policy contains it verbatim**")
        if head.prefix:
            matched, total = head.prefix
            out.append(
                f"- **Inside `{head.cited}` the quote matches {matched} of its {total} words**"
                + (f", then stops at “{head.stops_at}”" if head.stops_at else "")
                + (
                    " — a paraphrase in the derivation, not a wrong clause"
                    if matched >= total // 2
                    else " — the clause does not carry this text at all"
                )
            )
        if head.elsewhere:
            out.append(
                "- **It is in another policy's wording**: "
                + ", ".join(f"`{c}`" for c in head.elsewhere)
                + " — so either the wrong insurer was read, or this policy's clause text "
                "is damaged in the index"
            )
        if head.leading_ref and head.leading_ref != head.cited:
            out.append(
                f"- **The derivation opens by naming `{head.leading_ref}`**, not `{head.cited}`"
            )
        out += [
            f"- **The question**: does `{head.cited}` in {head.policy}.pdf say what these "
            "rows use it for? If not, which clause does?",
            "",
            "| bill | line | charged |",
            "|---|---|---|",
        ]
        for f in sorted(rows, key=lambda f: (f.bill, f.index)):
            out.append(f"| {f.bill} | {f.item[:52]} | {f.charged:,.0f} |")
        out.append("")

    return "\n".join(out) + "\n"


def record(fixed: list[Finding], unresolved: list[Finding]) -> str:
    """The change log appended to the review file: what moved, and what did not."""
    out = [
        "",
        "---",
        "",
        f"## Citation repair — {date.today().isoformat()}",
        "",
        "Written by `eval/repair_answer_key.py`. The rule: take the text a",
        "derivation puts in quotation marks, search every clause of that bill's",
        "policy for it, and where exactly one clause contains every quote, that",
        "clause is the citation. Zero matches or more than one: nothing changed,",
        "and the row is listed under **still unsettled** for a human to read the",
        "PDF for.",
        "",
        "No amount, no `needs_human` and no `allowed` was touched — a quotation is",
        "evidence about which clause, never about how much. No verdict, report or",
        "checkpoint was read while this ran.",
        "",
        f"**{len(fixed)} citations moved. {len(unresolved)} still unsettled.**",
        "",
        "### Moved",
        "",
    ]
    if not fixed:
        out += [
            "**Nothing.** Every citation that carries a quotation mark already points at a",
            "clause that contains it.",
            "",
            "That is not the result the 37-of-93 figure in the CANNOT SUPPORT section above",
            "predicts, and the reason is that the section above predates **D-12**. Those 37",
            "rows were the associated-medical-expense lines citing the room-rent cap; D-12",
            "moved 85 of them to `I.Def45` / `A.1.2.Def5`, which is exactly the clause their",
            "derivations quote. The repair had nothing left to do because the repair had",
            "already been made, by hand, as a decision.",
            "",
            "What is left is in `answer_key_todo.md`, and none of it can be settled by",
            "searching text - it needs the PDF.",
            "",
        ]
    else:
        out += [
            "| bill | line | was | now | the text that decided it |",
            "|---|---|---|---|---|",
        ]
    for f in sorted(fixed, key=lambda f: (f.bill, f.index)):
        quote = re.sub(r"\s+", " ", f.quote)[:110]
        out.append(f"| {f.bill} | {f.item[:44]} | `{f.cited}` | `{f.new}` | {quote}… |")
    out += [
        "",
        "### Still unsettled",
        "",
        "The quoted text is in no clause of the policy, or in more than one. These",
        "keep the citation they had; the reason is what to check against the PDF.",
        "",
        "| bill | line | cites | why it could not be settled |",
        "|---|---|---|---|",
    ]
    for f in sorted(unresolved, key=lambda f: (f.bill, f.index)):
        out.append(f"| {f.bill} | {f.item[:44]} | `{f.cited}` | {f.why[:150]} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
