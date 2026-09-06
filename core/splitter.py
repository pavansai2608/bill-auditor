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

# Header and any orphan first row sit above the ruled box, so the band just
# above a table is read as part of it.
TABLE_BAND_LIFT = 48
TABLE_MARKER = "[table]"
# find_tables() also fires on layout boxes holding ordinary prose. Treating
# those as tables swallows the clause headings inside them, so a detection only
# counts as a data table if it looks like one: several rows, several columns,
# and short cells.
MIN_TABLE_ROWS = 3
MIN_TABLE_COLS = 2
MAX_DATA_CELL_CHARS = 80
MAX_PROSE_CELL_RATIO = 0.25
MAX_HEADER_CHARS = 40

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

# How much of a line's vocabulary must already be in the rendered rows before
# the line counts as the flat read of those rows rather than a heading.
TABLE_WORD_RE = re.compile(r"[0-9a-z]+")
TABLE_ECHO_RATIO = 0.8

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

# Clause ids a clause names in its own text. Star Health's co-payment applies
# only to "Coverages II.1, II.2, ... II.13"; its specified-disease waiting
# period says the longer of two periods applies. Neither is decidable from the
# clause on its own, and the judge cannot ask for a clause it was not given.
REF_RES = (
    re.compile(r"\bSection\s+([A-E])[.\- ]\s?(\d+(?:\.\d+)*)"),
    re.compile(r"\bCoverages?\s+((?:[IVX]+\.\d+(?:\.\d+)*\s*,?\s*(?:and\s+)?)+)"),
    re.compile(r"\b(?:clause|Clause)\s+(\d+(?:\.\d+)+)"),
    re.compile(r"\bExclusions?\s+[Nn]o\.?\s*(\d+)"),
)
REF_LIST_RE = re.compile(r"[IVX]+\.\d+(?:\.\d+)*")
# Policies cite exclusions by IRDAI code rather than by clause number:
# "Exclusion No.1 (Code Excl 01)". The code has to be resolved to whichever
# clause carries it.
EXCL_CODE_RE = re.compile(r"Code[- ]?\s?Excl\s?0?(\d{1,2})", re.I)
EXCL_REF_RE = re.compile(r"(?:Exclusions?\s+[Nn]o\.?\s*(\d{1,2})|Code[- ]?\s?Excl\s?0?(\d{1,2}))")
MAX_REFS = 12


def _cell_text(words: list[dict], cell) -> str:
    """Words whose centre lies in the cell.

    Cropping instead would catch the tail of the line above: a word sitting on
    a cell boundary overlaps both, and "2,00,000/- 3,00,000/-" appears in one
    cell.
    """
    if cell is None:
        return ""
    x0, top, x1, bottom = cell
    inside = [
        word
        for word in words
        if x0 <= (word["x0"] + word["x1"]) / 2 <= x1
        and top <= (word["top"] + word["bottom"]) / 2 <= bottom
    ]
    inside.sort(key=lambda w: (round(w["top"], 1), w["x0"]))
    return re.sub(r"\s+", " ", " ".join(w["text"] for w in inside)).strip()


def table_rows(page, table) -> list[list[str]]:
    """The cell text of a table, row by row. See `_resolve_table`."""
    return _resolve_table(page, table)[0]


def _resolve_table(page, table) -> tuple[list[list[str]], list[list[tuple | None]]]:
    """Read a table by cell geometry, not by flattened text.

    `extract_text` reads straight across a table and interleaves the columns:
    Star Health's room rent table comes out as "...3,00,000/Up to 5,000/- per
    day 4,00,000/5,00,000/..." with 5,00,000 sitting next to the 5,000/- limit
    that actually belongs to 3L and 4L. A judge reading that picks the wrong
    row, confidently.

    A merged cell is one cell covering several rows, several columns, or both,
    so a cell is looked up by *containment on both axes*: the column's centre
    has to fall inside the cell's width and the row's midpoint inside its
    height. Matching a column by the x it starts at instead finds only the
    first column of a horizontally merged cell and leaves the rest blank -
    which is how star_health II.5 lost the limit for two of its six modern
    treatments. "Up to Sum Insured" is one cell 219pt wide spanning Bronchical
    Thermoplasty, Vaporisation of the prostate and IONM; read by starting x it
    belongs to Bronchical Thermoplasty alone.

    A column covered by a wide cell therefore repeats that cell's text. That is
    the point: the limit really does apply to each of those treatments, and a
    reader of the rendered row must not have to infer it.
    """
    cells = [c for c in table.cells if c]
    if not cells:
        return [], []

    words = page.extract_words()
    xs = sorted({round(cell[0], 1) for cell in cells})
    # Column centres, so a cell spanning several columns is found by every one
    # of them. The last column runs to the right-most edge in the table.
    edges = [*xs, max(cell[2] for cell in cells)]
    centres = [(edges[i] + edges[i + 1]) / 2 for i in range(len(xs))]

    rows: list[list[str]] = []
    sources: list[list[tuple | None]] = []
    left_column = sorted((c for c in cells if round(c[0], 1) == xs[0]), key=lambda c: c[1])
    for row_cell in left_column:
        midpoint = (row_cell[1] + row_cell[3]) / 2
        found = [
            next(
                (c for c in cells if c[0] <= centre <= c[2] and c[1] <= midpoint <= c[3]),
                None,
            )
            for centre in centres
        ]
        rows.append([_cell_text(words, cell) for cell in found])
        sources.append(found)
    return rows, sources


def _band_above(page, table, others=None) -> tuple[list[str], list[str]]:
    """Column headers and any data row stranded above the ruled box.

    Star Health rules its room rent table from the second row down, so the
    header and the 1,00,000 row fall outside the detected table entirely.

    The band stops at whatever table sits above this one. Two grids 16pt apart
    - II.5 has exactly that - otherwise let the lower one read the upper one's
    last row as its own first row, cropped mid-figure into "00,000/- 6,0".
    """
    cells = [c for c in table.cells if c]
    xs = sorted({round(c[0], 1) for c in cells})
    widths = {round(c[0], 1): c[2] for c in cells}
    top = table.bbox[1]
    if top <= 1:
        return [], []

    lift = TABLE_BAND_LIFT
    for other in others or []:
        if other is not table and other.bbox[3] <= top:
            lift = min(lift, top - other.bbox[3])

    headers: list[str] = []
    orphan: list[str] = []
    for x in xs:
        try:
            band = page.crop((x, max(0, top - lift), widths[x], top))
            lines = [ln["text"].strip() for ln in band.extract_text_lines() if ln["text"].strip()]
        except ValueError:
            lines = []
        # The band also catches the tail of the paragraph above the table
        # ("accommodation."). A column label starts with a capital or a digit
        # and does not end a sentence.
        lines = [ln for ln in lines if re.match(r"[A-Z0-9]", ln) and not ln.endswith(".")]
        # A column label can wrap over several lines ("Uterine artery /
        # Embolization / and HIFU"), so the header is the run of lines at the
        # top that carry no figure. Everything from the first figure down is a
        # data row stranded above the ruled box - and "Up to 2,000/- per day"
        # is data even though it opens with a letter.
        first_data = next((i for i, ln in enumerate(lines) if re.search(r"\d", ln)), len(lines))
        label_lines = lines[:first_data]
        data_lines = lines[first_data:]
        headers.append(" ".join(label_lines))
        orphan.append(" ".join(data_lines))
    return headers, orphan


def _is_data_row(row: list[str]) -> bool:
    """A row whose left-hand cell carries a figure, i.e. a row key rather than a label.

    Every rule-bearing grid in these documents is keyed on a number in its first
    column - a sum insured, a plan year, an age band - so this is what separates
    the heading block at the top from the data underneath it.
    """
    return bool(row) and bool(re.search(r"\d", row[0]))


def is_data_table(rows: list[list[str]]) -> bool:
    """Distinguish a real data table from a layout box full of prose."""
    if len(rows) < MIN_TABLE_ROWS or max((len(r) for r in rows), default=0) < MIN_TABLE_COLS:
        return False
    cells = [c for row in rows for c in row if c.strip()]
    if len(cells) < MIN_TABLE_ROWS:
        return False
    prose = sum(1 for c in cells if len(c) > MAX_DATA_CELL_CHARS)
    return prose / len(cells) <= MAX_PROSE_CELL_RATIO


def render_table(page, table, others=None) -> str:
    """One line per row, each cell labelled with its column header.

    "Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day" cannot
    be misread the way a flattened row can.
    """
    rows, sources = _resolve_table(page, table)
    if not is_data_table(rows):
        return ""
    # A cell that covers every column of its row is a caption, a spanning
    # sub-heading or a footnote - one statement about the table, not a value per
    # column - so it is written once. A cell covering only *some* columns is a
    # value that genuinely applies to each of them and is repeated, which is
    # what keeps "Up to Sum Insured" aligned with all three treatments it
    # covers rather than only the left-most.
    # Every column has to be *covered* by that one cell, not merely fail to
    # find one of its own. A row whose other cells are missing - the room rent
    # table's 2,00,000 row, blank because it is merged upward with 1,00,000 -
    # also has a single distinct source, and treating it as a caption drops the
    # limit that belongs to it.
    spanning = {
        index
        for index, row in enumerate(sources)
        if len(row) > 1
        and all(cell is not None for cell in row)
        and len({id(cell) for cell in row}) == 1
    }

    headers, orphan = _band_above(page, table, others)
    # A "header" longer than a label is the paragraph above the table, not a
    # column name.
    if any(len(h) > MAX_HEADER_CHARS for h in headers):
        headers = [""] * len(headers)
    if any(orphan) and all(len(o) <= MAX_DATA_CELL_CHARS for o in orphan):
        rows.insert(0, orphan)
        spanning = {index + 1 for index in spanning}

    # A blank under a merged cell means "same as above" - but only within the
    # data. Carried across the header the same rule copies a *column label*
    # into every row beneath it, which reads like a value and is not one: II.5
    # showed "Vaporisation of the prostate" as the limit for nine sum insureds.
    # So the fill restarts at the first data row, and a data row can only
    # inherit from another data row.
    width = max(len(r) for r in rows)
    first_data = next((i for i, row in enumerate(rows) if _is_data_row(row)), len(rows))

    filled: list[list[str]] = []
    previous: list[str] = [""] * width
    for index, row in enumerate(rows):
        if index == first_data:
            previous = [""] * width
        current = [
            cell.strip() or (previous[i] if i < len(previous) else "") for i, cell in enumerate(row)
        ]
        filled.append(current)
        previous = current

    out: list[str] = []
    for row_index, row in enumerate(filled):
        if row_index in spanning:
            single = next((c for c in row if c.strip()), "")
            if single:
                out.append(f"{TABLE_MARKER} {single}")
            continue
        parts = []
        for index, cell in enumerate(row):
            if not cell:
                continue
            label = headers[index] if index < len(headers) else ""
            parts.append(f"{label} {cell}".strip())
        if parts:
            out.append(f"{TABLE_MARKER} " + " - ".join(parts))

    rendered = "\n".join(out)
    # The ombudsman annexures are ruled grids of postal addresses. Reading
    # merged cells properly fills enough of them that they now clear the
    # data-table guard, and they carry no policy rule - two pages of "Tel.:"
    # and "Email:" would be pure noise in the index. Same test the splitter
    # already uses to drop those pages as prose.
    if len(NOISE_RE.findall(rendered)) >= NOISE_HITS:
        return ""
    return rendered


@dataclass
class PageText:
    page: int  # 1-based, as printed in the PDF
    text: str


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# phantom spaces
# --------------------------------------------------------------------------

# How much slack, in points, when asking whether one glyph box sits inside
# another. Half a point is smaller than any glyph in these documents and larger
# than the rounding in a PDF text matrix.
PHANTOM_EPSILON = 0.5
# Two glyphs are on one text line when their tops agree this closely. Every
# character in a line of body text in these PDFs shares a top to three decimals.
SAME_LINE = 1.0


def is_phantom_space(space: dict, previous: dict, following: dict) -> bool:
    """A space glyph painted on top of the letter before it, not between words.

    star_health.pdf emits a space at the same cursor position as the first
    letter after a list marker, so the two overlap: for "Expenses related to the
    treatment of the listed conditions" the content stream carries

        'E'  x0=347.242  x1=352.664
        ' '  x0=347.244  x1=350.066      <- inside the E
        'x'  x0=352.596  x1=357.659

    The space paints nothing, so the page reads correctly, but pdfplumber sorts
    by position, the space lands between the E and the x, and the index gets
    "E xpenses". BM25 then cannot match "Expenses" at all, and a citation cannot
    be located by quoting it. 79 of these exist across the four documents, all
    of them in star_health.pdf.

    **The rule: a space whose box lies entirely inside the box of the character
    immediately before it, on the same line, where neither neighbour is itself a
    space.**

    It cannot fire on a real space. A space exists to advance the cursor past the
    glyph before it, so its box begins at or after that glyph's right edge. To be
    caught here it would have to begin at or after the previous glyph's *left*
    edge and end at or before its *right* edge - the previous glyph covering it
    completely - which in correctly typeset text would mean the following word
    was painted on top of the preceding one. Measured across all four documents:
    50,297 spaces, 79 caught.

    The "neither neighbour is a space" condition is what keeps a doubled space
    safe. star_health writes list markers as "i.  Having", two spaces, and the
    second one overlaps the first. Without this condition both would be dropped
    and the words would weld together.
    """
    if space["text"] != " " or previous["text"] == " " or following["text"] == " ":
        return False
    if abs(space["top"] - previous["top"]) >= SAME_LINE:
        return False
    if abs(space["top"] - following["top"]) >= SAME_LINE:
        return False
    return (
        space["x0"] >= previous["x0"] - PHANTOM_EPSILON
        and space["x1"] <= previous["x1"] + PHANTOM_EPSILON
    )


def without_phantom_spaces(page):
    """The page with those space glyphs removed, ready for any extraction.

    Applied to the whole page rather than to the extracted string, so every
    reader downstream - flowing text, table cells, the column heuristic - sees
    the same characters. A regex sweep over the finished text could not tell
    "E xpenses" from a genuine "E xpenses", because by then the geometry that
    proves it is gone.
    """
    chars = sorted(page.chars, key=lambda c: (round(c["top"], 1), c["x0"]))
    doomed = {
        (round(c["x0"], 3), round(c["top"], 3))
        for index, c in enumerate(chars)
        if 0 < index < len(chars) - 1 and is_phantom_space(c, chars[index - 1], chars[index + 1])
    }
    if not doomed:
        return page
    return page.filter(
        lambda obj: (
            obj.get("object_type") != "char"
            or obj.get("text") != " "
            or (round(obj["x0"], 3), round(obj["top"], 3)) not in doomed
        )
    )


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
    ratios = sorted(right_start_ratio(without_phantom_spaces(p)) for p in pdf.pages)
    if not ratios:
        return False
    median = ratios[len(ratios) // 2]
    log.debug("median right-start ratio %.3f", median)
    return median > COLUMN_START_RATIO


def _echoes_the_table(text: str, rendered: str) -> bool:
    """Is this line the flat read of rows the table already rendered?

    `extract_text_lines` reads a table straight across, so every row also
    reaches the text as a line of interleaved cells. Where that line begins with
    a cell that looks like a clause number - "2.1 Not Covered" - it matches
    `CLAUSE_RE` and would open a clause built entirely out of table debris. The
    tell is that its words are already in the rendered rows.

    Word overlap rather than an exact match, because the flat read joins cells
    from different columns in an order the rendered row does not use.
    """
    words = [word for word in TABLE_WORD_RE.findall(text.lower()) if len(word) > 1]
    if not words:
        return True
    have = set(TABLE_WORD_RE.findall(rendered.lower()))
    return sum(1 for word in words if word in have) / len(words) >= TABLE_ECHO_RATIO


def _region_text(page, tables, bbox) -> str:
    """Text of one region with tables rendered structurally, in reading order.

    Table content is removed from the flowing text and re-inserted at the same
    vertical position as labelled rows, so a table is never read twice and
    never read flat.
    """
    x0, top, x1, bottom = bbox
    try:
        region = page.crop(bbox)
    except ValueError:
        return ""

    here = [
        table
        for table in tables
        if x0 <= (table.bbox[0] + table.bbox[2]) / 2 <= x1
        and top <= (table.bbox[1] + table.bbox[3]) / 2 <= bottom
    ]

    # Render once. The rendered rows are needed twice: to place them back in the
    # text, and to recognise the flat read of those same rows.
    rendered_here = [(table, render_table(page, table, tables)) for table in here]
    rendered_here = [pair for pair in rendered_here if pair[1]]

    def inside_a_table(line) -> bool:
        text = line["text"]
        # A section banner is a document landmark, never a table row.
        if _section_at(text):
            return False
        for table, rendered in rendered_here:
            tx0, ttop, tx1, tbottom = table.bbox
            if not (
                ttop - TABLE_BAND_LIFT <= line["top"] <= tbottom
                and line["x0"] < tx1
                and line["x1"] > tx0
            ):
                continue
            # A clause heading that happens to sit inside a detected table
            # region must survive, or the clause it opens disappears from the
            # index - **unless the table already carries its words**, in which
            # case it is not a heading at all. It is the flat read of a row that
            # has already been emitted structurally, and keeping it puts the
            # same row in the index twice, once correctly and once as rubbish.
            return not CLAUSE_RE.match(text) or _echoes_the_table(text, rendered)
        return False

    items: list[tuple[float, str]] = []
    try:
        for line in region.extract_text_lines():
            if line["text"].strip() and not inside_a_table(line):
                items.append((line["top"], line["text"]))
    except ValueError:
        return region.extract_text() or ""

    for table, rendered in rendered_here:
        items.append((table.bbox[1] - TABLE_BAND_LIFT, rendered))

    items.sort(key=lambda pair: pair[0])
    return "\n".join(text for _, text in items)


def _page_text(page, two_column: bool) -> str:
    """Read one page, splitting columns only when this page really has two."""
    top = page.height * MARGIN_RATIO
    bottom = page.height * (1 - MARGIN_RATIO)

    try:
        tables = page.find_tables()
    except Exception:  # a malformed page must not stop ingestion
        tables = []

    if not tables:
        body = page.crop((0, top, page.width, bottom))
        if not two_column or right_start_ratio(page) <= COLUMN_START_RATIO:
            return body.extract_text() or ""
        mid = page.width / 2
        left = body.crop((0, top, mid, bottom)).extract_text() or ""
        right = body.crop((mid, top, page.width, bottom)).extract_text() or ""
        return f"{left}\n{right}"

    if not two_column or right_start_ratio(page) <= COLUMN_START_RATIO:
        return _region_text(page, tables, (0, top, page.width, bottom))

    mid = page.width / 2
    left = _region_text(page, tables, (0, top, mid, bottom))
    right = _region_text(page, tables, (mid, top, page.width, bottom))
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
            clean = without_phantom_spaces(page)
            pages.append(PageText(page=index, text=_page_text(clean, two_column)))
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
        is_table_row = line.lstrip().startswith(TABLE_MARKER)
        # A table row is a record, not a sentence. Joining rows would undo the
        # whole point of reading the table structurally.
        starts_new = is_heading or is_table_row or bool(SUBITEM_RE.match(line))
        # A heading must stay on its own line: absorbing the sentence beneath it
        # would hide the clause from the splitter.
        if (
            out
            and not starts_new
            and not previous_was_heading
            and not out[-1].lstrip().startswith(TABLE_MARKER)
        ):
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


NUMERIC_TOKEN_RE = re.compile(r"^[\d,.]+%?/?-?$")
MAX_NUMERIC_TOKEN_RATIO = 0.20


def is_table_debris(title: str) -> bool:
    """True for a "clause heading" that is really a row of a table.

    Annexure grids and plan-comparison tables produce headings like
    "GAUZE 16 X-RAY FILM" and "April 31st December Up to 3000 0% 0%". They match
    the clause pattern because a table cell starts with a number, but they carry
    no rule and only add noise to retrieval.
    """
    if TABLE_MARKER in title:
        return True
    tokens = title.split()
    if not tokens:
        return True
    numeric = sum(1 for tok in tokens if NUMERIC_TOKEN_RE.match(tok))
    if numeric / len(tokens) > MAX_NUMERIC_TOKEN_RATIO:
        return True
    # An all-capitals heading carrying a serial number is an annexure row.
    letters = [c for c in title if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and any(c.isdigit() for c in title)


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
        title = complete_title(
            match.group(2).rstrip(":"),
            # Never extend a title into a table row.
            [
                ln
                for ln, _ in lines[index + 1 : index + 4]
                if not ln.lstrip().startswith(TABLE_MARKER)
            ],
        )
        # Checked on both the raw heading and the completed title: extension can
        # pull table content in and turn a plausible heading into debris.
        if is_table_debris(match.group(2)) or is_table_debris(title):
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
                "title": title,
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
        # Its own line goes with it. That costs one real sentence today -
        # "4.2.2 We pay for Modern treatments as specified below:" sits under a
        # table lifted above it, so its body is empty and the only occurrence of
        # "Modern" in niva_bupa goes with the start. Keeping such headings by
        # folding them into the clause above was measured and rejected: it
        # recovers 3,359 characters and moves 30 clauses, most of them contents
        # entries glued onto unrelated bodies. See eval/table_corruption_survey.md.
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


def _without_the_address_block(clause: Clause, taken: set[str]) -> list[Clause]:
    """Cut an address annexure where the addresses stop, and keep the rest.

    **An address list ends; the document does not.** hdfc_ergo's ombudsman
    annexure is followed, with no heading of its own between them, by IRDAI List
    I and by the plan-comparison grid that states every benefit limit in the
    policy. Dropping the whole clause as contact data drops those too - two
    pages, 6,314 characters, sixteen rendered table rows and the legend defining
    what "Not Covered" means in that grid.

    That did not happen before, only because the flat read of the grid's own
    rows was opening clauses of table debris part-way down, which cut the
    annexure into pieces small enough to survive. Removing the debris removed
    the accident that was preserving the tables, and the tables have to be kept
    on purpose instead.

    So the clause is cut after the last line carrying an address marker.
    Everything above it is contact data and goes; everything below stays,
    retitled from what is actually left.

    **What is left is then split where the tables stop and the prose starts.**
    Kept whole it is 12,414 characters - three annexures and a legend welded
    into one record - and `tests/test_ingest.py` caps a clause at 12,000
    because three of those in one judge prompt would swamp `num_ctx`. The
    boundary is not arbitrary: rendered rows and the paragraphs explaining them
    are different things to retrieve, and "'Not Covered' means that particular
    benefit is NOT available" is worth finding without dragging 9,748
    characters of table behind it.
    """
    lines = clause.text.split("\n")
    last_address = max(
        (index for index, line in enumerate(lines) if NOISE_RE.search(line)),
        default=None,
    )
    if last_address is None:
        return []

    body = "\n".join(lines[last_address + 1 :]).strip()
    if len(body) < MIN_BODY_CHARS:
        return []

    out: list[Clause] = []
    for part in _table_and_prose_runs(body):
        if len(part) < MIN_BODY_CHARS:
            continue
        clause_id = clause.clause_id if not out else _next_free_sibling(clause.clause_id, taken)
        taken.add(clause_id)
        out.append(
            Clause(
                clause_id=clause_id,
                title=_title_for(part, clause.title),
                text=part,
                page=clause.page,
                policy=clause.policy,
            )
        )
    return out


def _table_and_prose_runs(body: str) -> list[str]:
    """Break a body where rendered table rows give way to prose, and back.

    One run per stretch, in document order. A body that is all one kind comes
    back as a single run, so nothing is split that does not need to be.
    """
    runs: list[list[str]] = []
    previous: bool | None = None
    for line in body.split("\n"):
        is_row = line.lstrip().startswith(TABLE_MARKER)
        if is_row != previous:
            runs.append([])
            previous = is_row
        runs[-1].append(line)
    return [text for text in ("\n".join(run).strip() for run in runs) if text]


def _next_free_sibling(clause_id: str, taken: set[str]) -> str:
    """The next unused id beside this one: E.2 -> E.3, skipping what exists.

    Continuing the numbering is what the document itself does - the legend that
    lands in the second part was `E.3` before the splitter fix, under a title
    lifted from a stray table cell. Inventing a suffix instead would produce an
    id no reader could look up, and reusing `E.2.1` would point at a clause
    `KNOWN_LIMITATIONS.md` section 10 discusses as a defect.
    """
    head, _, last = clause_id.rpartition(".")
    if not last.isdigit():
        return clause_id
    number = int(last) + 1
    while (f"{head}.{number}" if head else str(number)) in taken:
        number += 1
    return f"{head}.{number}" if head else str(number)


def _title_for(body: str, fallback: str) -> str:
    """The first line of a body that reads like a heading rather than a cell.

    A part that is nothing but rendered rows has no such line, and inheriting
    the parent's title is worse than having none: the annexure cut out of
    hdfc_ergo's ombudsman block would be titled "Contact Us", which is both
    wrong and embedded into the vector alongside the rows. Its first row is at
    least about the right subject.
    """
    heading = next(
        (
            line.strip()
            for line in body.split("\n")
            if not line.lstrip().startswith(TABLE_MARKER)
            and _looks_like_title(line.strip())
            and not is_table_debris(line.strip())
        ),
        None,
    )
    if heading is None:
        first = body.split("\n")[0].strip()
        heading = first[len(TABLE_MARKER) :].strip() if first.startswith(TABLE_MARKER) else fallback
    return (heading or fallback)[:120]


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


def find_refs(text: str, known: set[str]) -> list[str]:
    """Clause ids this text names, restricted to ids that actually exist."""
    found: list[str] = []
    for pattern in REF_RES:
        for match in pattern.finditer(text):
            groups = match.groups()
            if len(groups) == 2 and groups[0] and groups[1]:
                found.append(f"{groups[0]}.{groups[1]}")
            else:
                found.extend(REF_LIST_RE.findall(groups[0]) or [groups[0]])
    seen: list[str] = []
    for ref in found:
        if ref in known and ref not in seen:
            seen.append(ref)
    return seen[:MAX_REFS]


def _exclusion_index(clauses: list[Clause]) -> dict[str, str]:
    """Map an IRDAI exclusion code to the clause that defines it."""
    index: dict[str, str] = {}
    for clause in clauses:
        # A clause defines a code when it carries it in its own heading.
        head = clause.text[:160]
        for code in EXCL_CODE_RE.findall(head):
            index.setdefault(code.lstrip("0") or "0", clause.clause_id)
    return index


def attach_refs(clauses: list[Clause]) -> list[Clause]:
    known = {c.clause_id for c in clauses}
    codes = _exclusion_index(clauses)
    for clause in clauses:
        refs = find_refs(clause.text, known)
        for a, b in EXCL_REF_RE.findall(clause.text):
            code = (a or b).lstrip("0") or "0"
            target = codes.get(code)
            if target and target not in refs:
                refs.append(target)
        clause.refs = [r for r in refs if r != clause.clause_id][:MAX_REFS]
    total = sum(len(c.refs) for c in clauses)
    log.info("linked %d cross-references across %d clauses", total, len(clauses))
    return clauses


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

    # An address annexure is cut where the addresses stop rather than dropped
    # whole, because what follows one can be a rule - see
    # `_without_the_address_block`.
    taken = {clause.clause_id for clause in expanded}
    survivors: list[Clause] = []
    dropped = trimmed = 0
    for clause in expanded:
        if not _is_address_noise(clause):
            survivors.append(clause)
            continue
        remainder = _without_the_address_block(clause, taken)
        if not remainder:
            dropped += 1
            continue
        trimmed += 1
        survivors.extend(remainder)

    kept = attach_refs(survivors)
    log.info(
        "%s: %d clauses (%d after splitting definitions, %d address blocks dropped, "
        "%d trimmed to what followed them)",
        policy,
        len(kept),
        len(expanded),
        dropped,
        trimmed,
    )
    return kept
