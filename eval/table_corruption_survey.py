"""Detector for flattened-table corruption in the clause index.

`hdfc_ergo E.2.1` reads, in full:

    Not Covered
    800 per day 800 per day 1000 per day 800 per day
    2.2 choosing Shared max upto 4800 max upto 4800 Not Covered

That is a benefit-comparison grid read straight across. It is not a clause, and
a zero payout was read off it twice. The question this script exists to answer
is whether it is one bad table or a systematic extraction failure, because the
answer decides whether the splitter gets rebuilt.

Run it:

    uv run python eval/table_corruption_survey.py

The findings are written up in `eval/table_corruption_survey.md`.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings

TABLE_MARKER = "[table]"

# Each signal is a way a flattened table row differs from a sentence.
PER_UNIT_RE = re.compile(r"per\s+day", re.I)
UPTO_RE = re.compile(r"\bup\s*to\b", re.I)
NOT_COVERED_RE = re.compile(r"not\s+(?:covered|available)", re.I)
MONEY_RE = re.compile(r"\d[\d,]{2,}|\b\d+\s*(?:per day|lakh|lakhs)\b", re.I)
WORD_RE = re.compile(r"[A-Za-z]{2,}")
# Bare unit words a benefit grid uses as column headings, never as a heading.
UNIT_WORDS = {"lakh", "lakhs", "days", "day", "years", "covered", "optional", "nil"}
NUMERIC_TOKEN_RE = re.compile(r"^[\d,.%/-]+$")
LIST_NUMBER_RE = re.compile(r"\b\d{1,2}\.\s")
PHONE_RE = re.compile(r"\d{6,}")


def _flat(text: str, drop_rendered_rows: bool) -> str:
    """The clause text the signals are asked of.

    A correctly rendered table trips every signal below by design - that is what
    a table looks like. The second pass therefore drops the `[table]` lines
    first and asks the same questions of what is left. The difference between
    the two passes is the whole finding.
    """
    if not drop_rendered_rows:
        return text
    return "\n".join(ln for ln in text.split("\n") if not ln.lstrip().startswith(TABLE_MARKER))


def signals(clause: dict, drop_rendered_rows: bool = True) -> list[str]:
    """Which signs of a flattened row this clause shows."""
    flat = _flat(clause["text"], drop_rendered_rows)
    found = []

    if len(PER_UNIT_RE.findall(flat)) > 2:
        found.append("repeated-units")
    if len(UPTO_RE.findall(flat)) > 2:
        found.append("repeated-upto")

    for line in flat.split("\n"):
        if NOT_COVERED_RE.search(line) and MONEY_RE.search(line):
            found.append("notcovered-near-money")
            break

    # Numbers with no sentence around them: a line that is mostly numeric
    # tokens and carries no verb-length run of words.
    for line in flat.split("\n"):
        tokens = line.split()
        if len(tokens) < 4:
            continue
        numeric = sum(1 for tok in tokens if NUMERIC_TOKEN_RE.match(tok))
        if numeric / len(tokens) >= 0.4 and len(WORD_RE.findall(line)) < len(tokens) / 2:
            found.append("numeric-soup")
            break

    # A list read across its columns welds several item numbers into one line:
    # "1. Uterine Artery 2. Immunotherapy- 3. Vaporisation of the".
    for line in flat.split("\n"):
        if len(LIST_NUMBER_RE.findall(line)) >= 3:
            found.append("welded-list")
            break

    # A title that is a cell rather than a heading: "Not Covered", "Lakhs",
    # "TORNIQUET", a phone number.
    title = clause["title"].strip()
    letters = [c for c in title if c.isalpha()]
    if (
        NOT_COVERED_RE.fullmatch(title)
        or PHONE_RE.search(title)
        or (letters and all(c.isupper() for c in letters))
        or (len(title.split()) == 1 and title.lower() in UNIT_WORDS)
        or (3 <= len(title.split()) < 8 and MONEY_RE.search(title))
    ):
        found.append("row-in-title")

    return found


def survey(clauses: list[dict], drop_rendered_rows: bool) -> int:
    per_policy: Counter = Counter()
    totals: Counter = Counter()
    signal_counts: Counter = Counter()
    flagged = []

    for clause in clauses:
        totals[clause["policy"]] += 1
        found = signals(clause, drop_rendered_rows)
        if not found:
            continue
        per_policy[clause["policy"]] += 1
        for name in found:
            signal_counts[name] += 1
        flagged.append((clause, found))

    print(f"{len(flagged)} of {len(clauses)} clauses flagged\n")
    for policy in sorted(totals):
        n, total = per_policy[policy], totals[policy]
        print(f"  {policy:<12} {n:>2} of {total:>3}  ({n / total:.1%})")

    print("\nsignal frequency")
    for name, count in signal_counts.most_common():
        print(f"  {name:<24} {count}")

    print("\nflagged clauses - '[table]' markers separate a rendered table from a flattened one")
    for clause, found in sorted(
        flagged, key=lambda pair: (pair[0]["policy"], pair[0]["clause_id"])
    ):
        markers = clause["text"].count(TABLE_MARKER)
        state = "rendered" if markers else "FLATTENED"
        print(
            f"  {clause['policy']:<12} {clause['clause_id']:<10} "
            f"markers={markers:<3} {state:<10} {len(clause['text']):>5} chars  "
            f"{','.join(found)}"
        )

    rendered = sum(1 for clause, _ in flagged if TABLE_MARKER in clause["text"])
    print(f"\n{rendered} of {len(flagged)} carry [table] markers and are correct renderings.")
    print(f"{len(flagged) - rendered} are flattened.")
    return len(flagged)


def main() -> int:
    clauses = json.loads((settings.data_dir / "clauses.json").read_text())

    print("=" * 72)
    print("PASS 1 - the signals asked of the whole clause, rendered rows included")
    print("=" * 72)
    naive = survey(clauses, drop_rendered_rows=False)

    print()
    print("=" * 72)
    print("PASS 2 - the same signals, asked only of text outside the [table] rows")
    print("=" * 72)
    real = survey(clauses, drop_rendered_rows=True)

    print(
        f"\nPass 1 flagged {naive}. Pass 2 flagged {real}. "
        f"{naive - real} of pass 1's flags were tables the splitter read correctly."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
