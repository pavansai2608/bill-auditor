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
                "title": match.group(2).strip().rstrip(":").strip(),
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
        clauses.append(
            Clause(
                clause_id=clause_id,
                title=start["title"][:120],
                text=f"{start['title']}\n{body}".strip(),
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


def split_pdf(pdf_path: Path, policy: str) -> list[Clause]:
    """S2 -> S5 for one policy document."""
    pages = clean_pages(extract_pages(pdf_path))
    clauses = split_clauses(pages, policy)

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
