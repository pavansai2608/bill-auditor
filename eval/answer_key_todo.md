# Answer key — what still needs a human and a PDF

Written by `eval/repair_answer_key.py`. Every row here is a citation that
**could not be settled from the text**: the clause the derivation quotes is not
the clause the row cites, or there is no quoted text to search for at all.

The mechanical repair changed nothing, because there was nothing it could change
safely - see the citation-repair section of `answer_key_review.md`. What is left
is what a person has to read the document for.

**Rows are grouped into questions.** Thirteen rows citing the same clause with the
same quote are one question, not thirteen, and settling it settles all of them.
The groups are ordered by how much they decide.

**72 rows, 5 questions.**

Each question is one page of one PDF. Q1 is the only one that needs real
reading - the others are "does this clause say what 20 rows use it for", and the
answer is usually visible in a paragraph. Budget **30 to 45 minutes** for all
five, most of it on Q1.

Answer them in this file, in the row, or tell me the answers and I will apply
them. Nothing here has been changed on your behalf.

| tier | what it means | rows |
|---|---|---|
| 1 | The evidence and the citation disagree | 13 |
| 3 | There is no quoted text to check | 59 |


## Tier 1 — The evidence and the citation disagree

The derivation quotes text that is **not in the clause the row cites**, and in some cases not in that policy at all. Either the wrong clause is cited, the quote was paraphrased rather than copied, or the clause index has damaged that clause's text. All three need the PDF.

### Q1. `star_health` `III.2` — 13 rows

- **Open** star_health.pdf at **page 28** (where `III.2` was split from)
- **The row quotes** “Expenses related to the treatment of the listed conditions”
- **No clause of this policy contains it**
- **It is in another policy's wording**: `hdfc_ergo:C.1`, `niva_bupa:5.1.2` — so either the wrong insurer was read, or this policy's clause text is damaged in the index
- **The question**: does `III.2` in star_health.pdf say what these rows use it for? If not, which clause does?

| bill | line | charged |
|---|---|---|
| B27 | Room Rent (Shared) 3,500 x 3 days | 10,500 |
| B27 | Total Knee Replacement - Surgeon Fee | 145,000 |
| B27 | Knee Implant | 95,000 |
| B27 | Anaesthetist Charges | 22,000 |
| B27 | Operation Theatre Charges | 34,000 |
| B27 | Medicines and Drugs | 26,000 |
| B27 | Physiotherapy Sessions | 7,000 |
| B40 | Room Rent (Shared) 2,800 x 2 days | 5,600 |
| B40 | Piles / Fistula Surgery - Surgeon Fee | 46,000 |
| B40 | Anaesthetist Charges | 9,000 |
| B40 | Operation Theatre Charges | 13,000 |
| B40 | Medicines and Drugs | 7,200 |
| B40 | Investigations - Basic Panel | 2,800 |


## Tier 3 — There is no quoted text to check

A table derivation - `II.1 p10 table: Sum Insured 300,000 -> Up to 5,000/- per day` - carries no quotation marks, so there is no span to search for. The citation may be perfectly correct; this method simply cannot confirm it. The table renderings themselves are pinned by `tests/test_tables_golden.py`, which is the stronger check on this group, so read these only after the tiers above.

### Q2. `star_health` `II.1` — 25 rows

- **Open** star_health.pdf at **page 9** (where `II.1` was split from)
- **The row quotes** “(none)”
- **The question**: does `II.1` in star_health.pdf say what these rows use it for? If not, which clause does?

| bill | line | charged |
|---|---|---|
| B01 | Room Rent (Single A/C) 8,000 x 5 days | 40,000 |
| B01 | Disposable Syringes | 800 |
| B05 | Surgeon Fee | 55,000 |
| B05 | Anaesthetist Charges | 12,000 |
| B05 | Operation Theatre Charges | 18,000 |
| B05 | Consultant Visit Charges | 4,500 |
| B07 | Room Rent (Deluxe) 7,500 x 4 days | 30,000 |
| B09 | Surgeon Fee | 62,000 |
| B12 | Surgeon Fee | 45,000 |
| B14 | Surgeon Fee | 72,000 |
| B14 | Anaesthetist Charges | 16,000 |
| B14 | Operation Theatre Charges | 24,000 |
| B17 | Room Rent (Shared) 2,500 x 2 days | 5,000 |
| B17 | Surgeon Fee | 38,000 |
| B19 | Room Rent (Suite) 15,000 x 7 days | 105,000 |
| B22 | Surgeon Fee | 155,000 |
| B22 | Anaesthetist Charges | 32,000 |
| B22 | Operation Theatre Charges | 48,000 |
| B22 | Consultant Visit Charges | 7,500 |
| B26 | Surgeon Fee | 98,000 |
| B32 | Surgeon Fee | 52,000 |
| B32 | Anaesthetist Charges | 11,000 |
| B32 | Operation Theatre Charges | 17,000 |
| B33 | Room Rent (Suite) 18,000 x 6 days | 108,000 |
| B38 | Surgeon Fee | 60,000 |

### Q3. `hdfc_ergo` `B.1.1` — 20 rows

- **Open** hdfc_ergo.pdf at **page 11** (where `B.1.1` was split from)
- **The row quotes** “(none)”
- **The question**: does `B.1.1` in hdfc_ergo.pdf say what these rows use it for? If not, which clause does?

| bill | line | charged |
|---|---|---|
| B02 | Consultant Visit Charges | 6,000 |
| B04 | Room Rent (Single A/C) 9,500 x 7 days | 66,500 |
| B13 | Surgeon Fee | 58,000 |
| B15 | Room Rent (Deluxe) 12,000 x 7 days | 84,000 |
| B20 | Surgeon Fee | 84,000 |
| B20 | Anaesthetist Charges | 18,000 |
| B20 | Operation Theatre Charges | 26,000 |
| B20 | Consultant Visit Charges | 5,400 |
| B21 | Surgeon Fee | 44,000 |
| B24 | Consultant Visit Charges | 4,000 |
| B28 | Room Rent (Suite) 22,000 x 8 days | 176,000 |
| B28 | Ambulance Charges | 4,000 |
| B29 | Surgeon Fee | 46,000 |
| B29 | Anaesthetist Charges | 10,000 |
| B29 | Operation Theatre Charges | 15,000 |
| B35 | Surgeon Fee | 50,000 |
| B36 | Surgeon Fee | 34,000 |
| B36 | Operation Theatre Charges | 11,000 |
| B36 | Consultant Visit Charges | 2,200 |
| B43 | Consultant Visit Charges | 6,000 |

### Q4. `niva_bupa` `6.2.4` — 12 rows

- **Open** niva_bupa.pdf at **page 25** (where `6.2.4` was split from)
- **The row quotes** “(none)”
- **The question**: does `6.2.4` in niva_bupa.pdf say what these rows use it for? If not, which clause does?

| bill | line | charged |
|---|---|---|
| B03 | Surgeon Fee | 18,000 |
| B10 | Ambulance Charges | 2,500 |
| B11 | Room Rent (Single Private) 11,000 x 6 days | 66,000 |
| B16 | Surgeon Fee | 42,000 |
| B16 | Operation Theatre Charges | 14,000 |
| B16 | Consultant Visit Charges | 3,000 |
| B23 | Room Rent (Single Private) 13,500 x 5 days | 67,500 |
| B25 | Surgeon Fee | 36,000 |
| B25 | Operation Theatre Charges | 12,000 |
| B25 | Consultant Visit Charges | 2,400 |
| B30 | Surgeon Fee | 54,000 |
| B37 | Room Rent (Single Private) 10,500 x 5 days | 52,500 |

### Q5. `star_health` `II.5` — 2 rows

- **Open** star_health.pdf at **page 11** (where `II.5` was split from)
- **The row quotes** “(none)”
- **The question**: does `II.5` in star_health.pdf say what these rows use it for? If not, which clause does?

| bill | line | charged |
|---|---|---|
| B12 | Robotic Assisted Surgery Package | 185,000 |
| B38 | Stem Cell Therapy for Bone Marrow Transplant | 240,000 |

