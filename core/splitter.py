"""Custom clause splitter for insurance policy PDFs.

A character-based text splitter is useless here. Chopping every 800 characters
loses the clause number, and a verdict that cannot name the clause it came from
is worthless — the whole point of the system is the citation. So the document is
cut only where a new numbered clause begins.

Three complications the real PDFs forced:

* **Two-column layout.** Star Health's wording is set in two columns.
  `extract_text()` reads across both and interleaves them into nonsense. Pages
  are detected by how many text lines start in the right half of the page and,
  where a second column exists, each column is cropped and read separately.
* **Repeated headers and footers.** Every page carries the insurer's name and a
  UIN. They are found by frequency (a line on most pages is furniture, not
  content) rather than a hardcoded list, so a new insurer needs no code change.
* **Clauses spanning page breaks.** Pages are concatenated into one stream
  before splitting, so a clause that starts on page 12 and ends on page 13 stays
  a single record.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from core.logging_conf import get_logger
from core.models import Clause

log = get_logger(__name__)

# A clause opener: a number, an optional trailing dot, then a title that starts
# with a letter or a digit (amount-led headings appear in sub-limit tables).
CLAUSE_RE = re.compile(
    r"^[ \t]*(\d+(?:\.\d+)*)\.?[ \t]+(?=\S)(.{0,120}?)[ \t]*$",
    re.MULTILINE,
)

# Sub-items inside a clause. These must never trigger a split.
SUBITEM_RE = re.compile(r"^[ \t]*(?:[a-z]|[ivxlc]+|[A-Z])[.)][ \t]+", re.MULTILINE)

# Section banners. Clause numbers restart inside each section, so the section
# letter becomes part of the citation - which is how the documents refer to
# themselves ("Section B-2.9", "Section B.1.1").
SECTION_RES = (
    re.compile(r"^[ \t]*SECTION[ \t]+([A-Z])[.:]?[ \t]+([A-Z][A-Za-z /&-]{2,60})[ \t]*$"),
    re.compile(r"^[ \t]*([IVX]{1,5})\.[ \t]+([A-Z][A-Za-z /&-]{2,60})[ \t]*$"),
)

# Lines that begin a right-hand column start beyond this fraction of the width.
COLUMN_START_RATIO = 0.15
# Fraction of a page's height treated as header / footer furniture.
MARGIN_RATIO = 0.045
# Below this a heading has no body of its own and is a contents entry.
# Kept low deliberately: a real clause can be one sentence ("A co-payment of
# 20% applies to every claim"), and losing it loses the deduction it explains.
MIN_BODY_CHARS = 60

# Definition blocks carry their own internal numbering ("Def. 41. Room Rent
# means...") and run to 16k characters as a single heading. Left whole they
# would swamp the context window and bury the one definition that matters, so
# they are split again on that numbering.
DEF_RE = re.compile(r"(?m)^[ \t]*Def\.[ \t]*(\d+)\.[ \t]+(?=\S)")
MIN_DEFS_TO_SPLIT = 5

# Ombudsman annexures are pages of postal addresses. They match the clause
# pattern via PIN codes but contain no policy rule, and they would only add
# noise to retrieval.
NOISE_RE = re.compile(r"(?:Tel\.:|Email:|bimalokpal|cioins\.co\.in|Ombudsman)", re.I)
NOISE_HITS = 4

# Star Health writes its definitions as unnumbered "Term: Term means ..."
# headings, so nothing before Section II matches the clause pattern and the
# whole definitions section was dropped - 68 definitions including "Room Rent
# means ... and shall include the associated medical expenses", which is what
# makes the proportionate deduction reach the surgeon's fee.
UNNUMBERED_DEF_RE = re.compile(r"(?m)^[ \t]*([A-Z][A-Za-z0-9 /()'-]{3,45}):[ \t]+(?=[A-Z0-9])")
MIN_UNNUMBERED_DEFS = 10

# Some headings are letter-spaced by the PDF ("O rgan", "A YUSH"). "A" and "I"
# are real words, so they are never joined.
SPACED_LOWER_RE = re.compile(r"^([B-HJ-Z])\s+([a-z]{2,})")
SPACED_UPPER_RE = re.compile(r"^([A-Z])\s+([A-Z]{2,})\b")

# A heading cut at a column boundary ends on a function word.
DANGLING_RE = re.compile(
    r"\b(?:the|a|an|of|for|in|to|and|or|is|are|be|with|by|from|as|at|on|"
    r"which|that|will|shall|any|all|this|these|its|our|we|you|if|under|upto|up)\s*$",
    re.I,
)
TITLE_MAX = 90


@dataclass
class PageText:
    page: int  # 1-based, as printed in the PDF
    text: str


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------


def _line_starts(page) -> list[float]:
    """Left-most x of every visual text line on the page."""
    words = page.extract_words()
    if not words:
        return []
    rows: dict[int, list] = defaultdict(list)
    for word in words:
        rows[round(word["top"] / 3)].append(word)
    return [min(ws, key=lambda w: w["x0"])["x0"] for ws in rows.values()]


def right_start_ratio(page) -> float:
    """How much of the page reads as a second column.

    Near 0 means every line begins at the left margin (single column). Around
    0.4 means roughly half the lines begin past the middle, i.e. two columns.
    """
    starts = _line_starts(page)
    if not starts:
        return 0.0
    mid = page.width / 2
    return sum(1 for s in starts if s > mid) / len(starts)


def is_two_column_document(pdf) -> bool:
    """Decide once per document, so a full-width table cannot flip the layout."""
    ratios = sorted(right_start_ratio(p) for p in pdf.pages)
    if not ratios:
        return False
    median = ratios[len(ratios) // 2]
    log.debug("median right-start ratio %.3f", median)
    return median > COLUMN_START_RATIO


def _page_text(page, two_column: bool) -> str:
    """Read one page, splitting columns only when this page really has two."""
    top = page.height * MARGIN_RATIO
    bottom = page.height * (1 - MARGIN_RATIO)
    body = page.crop((0, top, page.width, bottom))

    if not two_column or right_start_ratio(page) <= COLUMN_START_RATIO:
        return body.extract_text() or ""

    mid = page.width / 2
    left = body.crop((0, top, mid, bottom)).extract_text() or ""
    right = body.crop((mid, top, page.width, bottom)).extract_text() or ""
    return f"{left}\n{right}"


def extract_pages(pdf_path: Path) -> list[PageText]:
    """S2 - text out of the PDF, one entry per page, columns in reading order."""
    pages: list[PageText] = []
    with pdfplumber.open(pdf_path) as pdf:
        two_column = is_two_column_document(pdf)
        log.info(
            "%s: %d pages, layout=%s",
            pdf_path.name,
            len(pdf.pages),
            "two-column" if two_column else "single-column",
        )
        for index, page in enumerate(pdf.pages, start=1):
            pages.append(PageText(page=index, text=_page_text(page, two_column)))
    return pages


# --------------------------------------------------------------------------
# cleaning (S3)
# --------------------------------------------------------------------------


def find_furniture(pages: list[PageText], threshold: float = 0.5) -> set[str]:
    """Lines repeated on at least `threshold` of pages are headers or footers."""
    counts: Counter[str] = Counter()
    for page in pages:
        for line in {ln.strip() for ln in page.text.split("\n") if ln.strip()}:
            counts[line] += 1
    minimum = max(2, int(len(pages) * threshold))
    furniture = {line for line, count in counts.items() if count >= minimum}
    if furniture:
        log.info("dropping %d repeated header/footer line(s)", len(furniture))
    return furniture


def _is_page_number(line: str) -> bool:
    return bool(re.fullmatch(r"(?:page\s*)?\d{1,3}(?:\s*(?:of|/)\s*\d{1,3})?", line.strip(), re.I))


def clean_pages(pages: list[PageText]) -> list[PageText]:
    furniture = find_furniture(pages)
    cleaned: list[PageText] = []
    for page in pages:
        kept = [
            line
            for line in page.text.split("\n")
            if line.strip() and line.strip() not in furniture and not _is_page_number(line)
        ]
        cleaned.append(PageText(page=page.page, text="\n".join(kept)))
    return cleaned


def join_wrapped_lines(text: str) -> str:
    """Rejoin sentences the PDF broke across lines.

    Only joins when the break is clearly mid-sentence: the line does not end a
    sentence and the next line does not start a new clause or sub-item. Hyphens
    split across lines are stitched back together.
    """
    lines = text.split("\n")
    out: list[str] = []
    previous_was_heading = False
    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        is_heading = bool(CLAUSE_RE.match(line))
        starts_new = is_heading or bool(SUBITEM_RE.match(line))
        # A heading must stay on its own line: absorbing the sentence beneath it
        # would hide the clause from the splitter.
        if out and not starts_new and not previous_was_heading:
            previous = out[-1]
            ends_sentence = previous.endswith((".", ":", ";", "?", "!"))
            if previous.endswith("-"):
                out[-1] = previous[:-1] + line.lstrip()
                continue
            if not ends_sentence and not previous.endswith(("|",)):
                out[-1] = f"{previous} {line.lstrip()}"
                continue
        out.append(line)
        previous_was_heading = is_heading
    return "\n".join(out)


# --------------------------------------------------------------------------
# splitting (S4, S5)
# --------------------------------------------------------------------------


def _depth(clause_id: str) -> int:
    return clause_id.count(".") + 1


def fix_letter_spacing(text: str) -> str:
    """Rejoin a drop-cap letter the PDF separated from its word."""
    text = SPACED_LOWER_RE.sub(r"\1\2", text)
    return SPACED_UPPER_RE.sub(r"\1\2", text)


def complete_title(heading: str, following: list[str]) -> str:
    """Extend a heading that a column break cut off mid-phrase.

    In a two-column layout a line is only about 44 characters wide, so
    "In-patient Treatment: We will cover the" is where the column ended, not
    where the title ended. Only headings that dangle on a function word are
    extended, which leaves single-column titles like "Hospitalization
    Expenses" untouched.
    """

    def trim_at_colon(text: str) -> str | None:
        head, separator, _ = text.partition(": ")
        if separator and 4 <= len(head) <= 80 and re.search(r"[A-Za-z]{3}", head):
            return head.rstrip(" ,;:").strip()
        return None

    title = fix_letter_spacing(heading.strip())

    # These policies write "Shared accommodation: If the Insured Person..." -
    # the heading is the part before the colon, and the rest is already the
    # first sentence of the body. Taking the prefix also sidesteps a column
    # break landing mid-word ("Coverage for Modern Treatments: The follo").
    trimmed = trim_at_colon(title)
    if trimmed:
        return trimmed

    index = 0
    while DANGLING_RE.search(title) and index < len(following) and len(title) < TITLE_MAX:
        title = f"{title} {following[index].strip()}"
        index += 1
        # Extension can pull in the colon that was on the next line.
        trimmed = trim_at_colon(title)
        if trimmed:
            return trimmed

    if len(title) > TITLE_MAX:
        title = title[:TITLE_MAX].rsplit(" ", 1)[0]
    return title.rstrip(" ,;:").strip()


def _looks_like_title(title: str) -> bool:
    """Reject sentence fragments and numeric noise.

    A real heading opens with a capital or a digit. Numbered list items inside a
    clause ("1. it needs ongoing monitoring") continue a sentence and start
    lower-case, which is what separates them from a genuine clause start.
    """
    if not title or not re.match(r"[A-Z0-9\u2018\u201c\"(]", title):
        return False
    if re.fullmatch(r"[\d\s.,%/\u20b9Rs()-]+", title, re.I):
        return False
    return bool(re.search(r"[A-Za-z]{3}", title))


def _section_at(line: str) -> str | None:
    """Return the section label if this line is a section banner."""
    for pattern in SECTION_RES:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return None


def split_clauses(pages: list[PageText], policy: str) -> list[Clause]:
    """S4/S5 - cut the page stream at clause numbers and attach metadata.

    Splitting happens on the raw line structure, before any line joining. The
    order matters: joining first would glue a heading onto the sentence beneath
    it, the heading would no longer be a line of its own, and the clause would
    become invisible to the splitter. Bodies are unwrapped afterwards.
    """
    # Walk pages as one stream so a clause crossing a page break stays whole.
    lines: list[tuple[str, int]] = []
    for page in pages:
        lines.extend((line, page.page) for line in page.text.split("\n"))

    section = ""
    starts: list[dict] = []
    for index, (line, page_no) in enumerate(lines):
        banner = _section_at(line)
        if banner:
            section = banner
            continue
        match = CLAUSE_RE.match(line)
        if not match or not _looks_like_title(match.group(2)):
            continue
        starts.append(
            {
                "index": index,
                "number": match.group(1),
                # Two separate things: a short label for display, and the
                # heading line in full for the body. Shortening the title must
                # never drop words from the text that gets embedded - cutting
                # "In-patient Treatment: We will cover the" at the colon lost
                # "We will cover the" from the clause itself.
                "title": complete_title(
                    match.group(2).rstrip(":"),
                    [ln for ln, _ in lines[index + 1 : index + 4]],
                ),
                "heading": fix_letter_spacing(match.group(2).strip()),
                "page": page_no,
                "section": section,
            }
        )

    clauses: list[Clause] = []
    for position, start in enumerate(starts):
        stop = starts[position + 1]["index"] if position + 1 < len(starts) else len(lines)
        body = join_wrapped_lines("\n".join(ln for ln, _ in lines[start["index"] + 1 : stop]))

        # A heading with nothing under it is a contents entry, not a clause.
        if len(body) < MIN_BODY_CHARS:
            continue

        clause_id = f"{start['section']}.{start['number']}" if start["section"] else start["number"]
        body = fix_letter_spacing(body)
        clauses.append(
            Clause(
                clause_id=clause_id,
                title=start["title"][:120],
                text=f"{start['heading']}\n{body}".strip(),
                page=start["page"],
                policy=policy,
            )
        )

    return _drop_duplicates(clauses)


def _drop_duplicates(clauses: list[Clause]) -> list[Clause]:
    """Keep the fullest body when a clause_id repeats.

    Contents pages and benefit-summary tables reuse the numbering; the real
    clause is always the longer one. Document order is preserved.
    """
    best: dict[str, int] = {}
    for position, clause in enumerate(clauses):
        seen = best.get(clause.clause_id)
        if seen is None or len(clause.text) > len(clauses[seen].text):
            best[clause.clause_id] = position
    return [clauses[i] for i in sorted(best.values())]


def _is_address_noise(clause: Clause) -> bool:
    """True for ombudsman/branch address annexures - contact data, not rules."""
    return len(NOISE_RE.findall(clause.text)) >= NOISE_HITS


def _split_definitions(clause: Clause) -> list[Clause]:
    """Break a definitions block into one clause per defined term.

    Without this, "Room Rent means the amount charged by a Hospital" is one
    paragraph inside a 16,000-character clause, and citing it means citing the
    whole block.
    """
    matches = list(DEF_RE.finditer(clause.text))
    if len(matches) < MIN_DEFS_TO_SPLIT:
        return [clause]

    out: list[Clause] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clause.text)
        body = clause.text[match.end() : end].strip()
        if len(body) < 40:
            continue
        # The defined term is the phrase before "means" / "refers to".
        head = re.split(r"\s+(?:means|refers to|is|shall mean)\b", body, maxsplit=1)[0]
        title = head.strip()[:80] if len(head) < 80 else body[:60]
        out.append(
            Clause(
                clause_id=f"{clause.clause_id}.Def{match.group(1)}",
                title=title,
                text=body,
                page=clause.page,
                policy=clause.policy,
            )
        )
    return out or [clause]


def split_unnumbered_definitions(
    pages: list[PageText], policy: str, stop_line: int
) -> list[Clause]:
    """Capture a definitions section written as unnumbered "Term: ..." headings.

    Star Health numbers its coverage clauses but not its definitions, so the
    clause pattern matches nothing until Section II and everything before it -
    68 definitions - was silently dropped. They are given synthetic ids
    (`I.Def1`) so a verdict can still cite one.
    """
    lines: list[tuple[str, int]] = []
    for page in pages:
        lines.extend((line, page.page) for line in page.text.split("\n"))
    lines = lines[:stop_line]

    text_only = "\n".join(line for line, _ in lines)
    if len(UNNUMBERED_DEF_RE.findall(text_only)) < MIN_UNNUMBERED_DEFS:
        return []

    starts = [
        (index, UNNUMBERED_DEF_RE.match(line))
        for index, (line, _) in enumerate(lines)
        if UNNUMBERED_DEF_RE.match(line)
    ]

    clauses: list[Clause] = []
    for position, (index, match) in enumerate(starts):
        stop = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        term = fix_letter_spacing(match.group(1).strip())
        head = lines[index][0][match.end() :].strip()
        rest = join_wrapped_lines("\n".join(ln for ln, _ in lines[index + 1 : stop]))
        body = f"{term}: {head}\n{rest}".strip()

        if len(body) < MIN_BODY_CHARS:
            continue
        clauses.append(
            Clause(
                clause_id=f"I.Def{len(clauses) + 1}",
                title=term[:TITLE_MAX],
                text=fix_letter_spacing(body),
                page=lines[index][1],
                policy=policy,
            )
        )

    log.info("%s: recovered %d unnumbered definitions", policy, len(clauses))
    return clauses


def _first_clause_line(pages: list[PageText]) -> int:
    lines: list[str] = []
    for page in pages:
        lines.extend(page.text.split("\n"))
    for index, line in enumerate(lines):
        if _section_at(line):
            continue
        match = CLAUSE_RE.match(line)
        if match and _looks_like_title(match.group(2)):
            return index
    return 0


def split_pdf(pdf_path: Path, policy: str) -> list[Clause]:
    """S2 -> S5 for one policy document."""
    pages = clean_pages(extract_pages(pdf_path))
    clauses = split_clauses(pages, policy)

    # Anything above the first numbered clause is invisible to split_clauses.
    # For a policy that numbers only its coverage section, that is the whole
    # definitions section.
    clauses = split_unnumbered_definitions(pages, policy, _first_clause_line(pages)) + clauses

    expanded: list[Clause] = []
    for clause in clauses:
        expanded.extend(_split_definitions(clause))

    kept = [c for c in expanded if not _is_address_noise(c)]
    dropped = len(expanded) - len(kept)
    log.info(
        "%s: %d clauses (%d after splitting definitions, %d address blocks dropped)",
        policy,
        len(kept),
        len(expanded),
        dropped,
    )
    return kept
