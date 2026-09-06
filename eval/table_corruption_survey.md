# Survey: how much of the clause index is flattened table

**2026-09-06. Result: one bad table, not a systematic extraction failure. The
splitter was not rebuilt.**

`hdfc_ergo E.2.1` is not a clause. It is a row of a benefit-comparison grid read
straight across, and it reads, in full:

    Not Covered
    800 per day 800 per day 1000 per day 800 per day
    2.2 choosing Shared max upto 4800 max upto 4800 Not Covered

Guardrail 3 accepted a limit of Rs 0 against it twice, on B21 and B28, because
"Not Covered" is exclusionary language wherever it appears. The obvious worry
was that E.2.1 was one visible instance of a defect running through the whole
index — the shape phantom spaces turned out to have, where 79 occurrences across
26 clause bodies and 6 titles were quietly costing 2.5 points of accuracy. So
the size of the problem was measured before anything was changed.

Reproduce with:

    uv run python eval/table_corruption_survey.py

## What the detector looks for

Five signs that a run of text is a table row rather than a sentence: `per day`
more than twice, `up to` more than twice, "Not Covered"/"Not Available" on the
same line as a rupee figure, a line that is mostly numeric tokens with no
sentence around it, three or more list numbers welded into one line, and a title
that is a cell rather than a heading ("Not Covered", "Lakhs", "TORNIQUET", a
phone number).

It runs twice, and **the difference between the two passes is the finding**.
Pass 1 asks the questions of the whole clause. Pass 2 drops the `[table]` lines
first and asks the same questions of what is left.

## The counts

Pass 1 — the whole clause, rendered rows included:

| policy | flagged | of | rate |
|---|---|---|---|
| star_health | 9 | 153 | 5.9% |
| hdfc_ergo | 6 | 144 | 4.2% |
| niva_bupa | 3 | 105 | 2.9% |
| **total** | **18** | **402** | **4.5%** |

Pass 2 — the same questions, asked outside the `[table]` rows:

| policy | flagged | of | rate |
|---|---|---|---|
| star_health | 3 | 153 | 2.0% |
| hdfc_ergo | 3 | 144 | 2.1% |
| niva_bupa | 2 | 105 | 1.9% |
| **total** | **8** | **402** | **2.0%** |

**10 of pass 1's 18 flags were tables the splitter read correctly.** They trip
every signal because that is what a table looks like: `star_health II.1` (the
room rent table, 9 `[table]` rows), `II.5` (23), `hdfc_ergo E.1.4` (16),
`niva_bupa 4.10` (21). A detector that does not know about `[table]` markers
reports the working half of the system as broken.

## The eight that survive pass 2

| clause | `[table]` rows | verdict |
|---|---|---|
| **`hdfc_ergo E.2.1`** | 0 | **Corrupt.** 120 characters, no prose at all, title and body both cells |
| `hdfc_ergo E.3` | 0 | Title only. "Lakhs" is a stray cell above 2,671 characters of sound prose — and that prose is the legend that *defines* "Not Covered" for the grid |
| `hdfc_ergo D.3` | 0 | Title only. A phone number welded into the heading; the body is coherent |
| `niva_bupa 4.2.2` | 0 | A two-column list read across, items truncated ("Immunotherapy-") |
| `star_health IV.22`, `IV.37` | 20, 24 | Correct annexure tables under a debris title lifted from a cell |
| `star_health II.29`, `niva_bupa 4.10` | 30, 21 | False positives. Both read correctly |

**One clause is genuinely corrupt.**

## How far it reaches

Measured over the 44 checkpoints of `v12-ambulance-override`, 328 scored lines:

| clause | lines citing it |
|---|---|
| `IRDAI-List-I` | 61 |
| `hdfc_ergo B.1.1` | 40 |
| `star_health II.1` | 25 |
| … | |
| **`hdfc_ergo E.2.1`** | **2** (B21, B28) |
| every other flagged clause | 0 |

**2 of 328 lines, or 0.6%.** Both are the ambulance lines this started from.

## Why the splitter was not rebuilt

Set against the phantom-space work, which is the same shape of defect:

| | phantom spaces (v9) | flattened tables |
|---|---|---|
| occurrences | 79 | 1 clause |
| clauses damaged | 26 bodies, 6 titles | 1 |
| damage | broke BM25 on every term it split | 1 unreadable clause |
| scored lines reachable | most of the index | 2 of 328 |
| measured gain | 51.5% → 54.0% | ceiling ~0.6pp |

Phantom spaces were worth fixing at source because they were everywhere and
degraded retrieval for every query. This is one clause. The maximum upside is
about six tenths of a point, and only if the judge then reads the repaired
clause correctly — which is not the same thing.

**It is still worth fixing, on correctness grounds.** A clause that is not a
clause should not be in a citable index, and this one caused two confident wrong
zeros. But it is a correctness fix, not an accuracy fix, and it must not be sold
as one. The cause and the cost of fixing it are in `KNOWN_LIMITATIONS.md`
section 10.

## The fix, and the trap inside it

The cause was one line of `_region_text`. `pdfplumber` reads a table straight
across as well as by cell, so every row also arrives as a flat line of
interleaved text. The escape hatch that lets a genuine clause heading survive
inside a table region - `if _section_at(text) or CLAUSE_RE.match(text)` - was
exempting those flat rows too, because a row that opens with "2.1" looks exactly
like a clause number. **The table code was never broken. The line protecting
headings was.**

Deleting the exemption removes `E.2.1`. It also deletes **hdfc_ergo pages 50 and
51 outright** - 6,314 characters, the 16-row plan-comparison grid, and the
legend defining "Not Covered" for it. Those pages carry no heading of their own,
so once the debris stops opening clauses on them, their content falls into the
"Contact Us" ombudsman annexure and is dropped whole by `_is_address_noise`.
**The debris was the only thing keeping the real tables in the index.**

All 462 unit tests passed while that happened, and so did all 6 golden table
tests. Nothing in the suite asked whether content was still there. That gap is
now `tests/test_index_coverage.py`, written before the fix and shown failing
against the naive version first.

So the fix is two halves:

1. A line inside a rendered table is dropped even if it matches `CLAUSE_RE`,
   **unless its words are not already in the rendered rows** - the test is
   whether the line echoes the table, not whether it looks like a heading.
2. An address annexure is cut where the addresses stop rather than dropped
   whole, so what follows one stays in the index.

## One thing it costs, and one fix declined

23 lines left niva_bupa. 22 are word-for-word flat reads of rows that remain in
the index as `[table]` rows. The 23rd is real: `4.2.2 We pay for Modern
treatments as specified below:` carried the only occurrence of "Modern" in that
policy. Its table is rendered *above* it - `TABLE_BAND_LIFT` lifts a table over
the band that holds its header - so the heading is left with an empty body and
`MIN_BODY_CHARS` drops the start, taking its own line with it.

Folding such headings into the clause above them was written, measured and
**rejected**: it recovers 3,359 characters across the three policies and moves
30 clauses, most of them contents-page entries glued onto the end of unrelated
bodies. Recovering one token is not worth perturbing thirty clauses on an
unmeasured guess. The loss is recorded here and in
`tests/fixtures/index_coverage.json` instead.

## What the survey is worth as a negative result

The suspicion was a systematic extraction failure. The detector found 18 things
that looked like one. Reading all 18 showed that 10 were the table code working
exactly as designed and 4 more were sound clauses under a bad title. **The
honest answer was "one bad table", and the work that answer saved was a splitter
rebuild that would have moved the number by less than a point.**

The general lesson, and the reason the detector is committed rather than
discarded: **a signal that fires on both the defect and the fix measures
nothing.** "Numbers with no sentence around them" is a perfect description of a
correctly extracted table row. The `[table]` marker was what separated them, and
without it the survey would have reported a 4.5% corruption rate that was mostly
the system working.
