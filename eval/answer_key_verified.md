# Answer key — the 72 flagged rows, checked against the policy PDFs

All 72 rows in `answer_key_todo.md` were read back against the original policy
documents, clause by clause. **No row required a change.** The clause each row
cites does say what the row uses it for, and every arithmetic result follows
from the wording on the page.

Verified: 72 of 72. Changed: 0.

---

## Q1 — `star_health` `III.2`, 13 rows — CORRECT

**What III.2 actually is** (star_health.pdf, page 27 of 43, under `III. EXCLUSIONS`):

> **2. Specified disease / procedure waiting period - Code Excl 02**
> a. Expenses related to the treatment of the following listed Conditions,
> surgeries/treatments shall be excluded until the expiry of 24 months of
> continuous coverage after the date of inception of the first policy with us.
> This exclusion shall not be applicable for claims arising due to an accident

The list of specified diseases/procedures is on page 28, sub-clause `f`:

- item **3** — "All treatments (Conservative, Operative treatment) and all types
  of intervention for Diseases related to Tendon, Ligament, Fascia, Bones and
  Joint Including Arthroscopy and **Arthroplasty / Joint Replacement** [other
  than caused by accident]" → covers **B27, Total Knee Replacement**
- item **11** — "**Fistula**, Fissure in Ano, **Hemorrhoids**, Pilonidal Sinus
  and Fistula, Rectal Prolapse, Stress Incontinence" → covers **B40, Piles /
  Fistula Surgery**

**Dates:**

| bill | policy start | admission | elapsed | waiting period | result |
|---|---|---|---|---|---|
| B27 | 2025-09-05 | 2026-02-19 | 5 months 14 days | 24 months | every line nil |
| B40 | 2025-12-20 | 2026-04-22 | 4 months 2 days | 24 months | every line nil |

All 13 rows stand at `allowed = 0.0`, `clause_id = III.2`.

### Why this row was flagged, and why the flag was wrong

The repair script raised two concerns. Both are false positives.

1. *"The quote matches 7 of its 9 words then stops"* — the derivation writes
   "Expenses related to the treatment of the listed conditions"; the policy
   writes "Expenses related to the treatment of the **following** listed
   **Conditions, surgeries/treatments**". A faithful paraphrase, same meaning,
   same clause.
2. *"It is in another policy's wording: hdfc_ergo C.1, niva_bupa 5.1.2"* — all
   three insurers reproduce the **IRDAI standard Excl 02 template**, so the
   phrase appearing in all three is expected. It is not evidence that the wrong
   insurer was read.

---

## Q2 — `star_health` `II.1`, 25 rows — CORRECT

**What II.1 actually is** (page 8, under `II. Coverage`): **1. In-patient
Treatment**, listing room/boarding/nursing (i), surgeon, anaesthetist,
practitioner, consultant and specialist fees (ii), and anaesthesia, blood,
oxygen, OT, ICU, appliances, medicines, diagnostics (iii).

**The room table** (page 9) — the rupee limits the rows use:

| Sum Insured | Limit |
|---|---|
| 1,00,000 / 2,00,000 | Up to 2,000/- per day |
| 3,00,000 / 4,00,000 | Up to 5,000/- per day |
| 5,00,000 and above | Single Standard A/C Room |

Checked line by line against the bills:

| bill | SI | room | entitlement | key | ok |
|---|---|---|---|---|---|
| B01 | 300,000 | Single A/C 8,000 × 5 | 5,000/day → 25,000 | 25,000 | ✓ |
| B07 | 300,000 | Deluxe 7,500 × 4 | 5,000/day → 20,000 | 20,000 | ✓ |
| B19 | 400,000 | Suite 15,000 × 7 | 5,000/day → 35,000 | 35,000 | ✓ |
| B33 | 400,000 | Suite 18,000 × 6 | 5,000/day → 30,000 | 30,000 | ✓ |
| B05 B09 B12 B14 B17 B22 B26 B32 B38 | 300,000–2,500,000 | Shared / Single A/C | at or below entitlement | full | ✓ |

The proportionate deductions all reproduce exactly:

| bill | ratio | line | charged | × ratio | key |
|---|---|---|---|---|---|
| B01 | 5,000/8,000 = 0.6250 | Surgeon | 80,000 | 50,000.00 | 50,000 ✓ |
| B01 | 0.6250 | Anaesthetist | 15,000 | 9,375.00 | 9,375 ✓ |
| B07 | 5,000/7,500 = 0.6667 | Surgeon | 48,000 | 32,000.00 | 32,000 ✓ |
| B19 | 5,000/15,000 = 0.3333 | Surgeon | 165,000 | 55,000.00 | 55,000 ✓ |
| B33 | 5,000/18,000 = 0.2778 | Surgeon | 195,000 | 54,166.67 | 54,166.67 ✓ |

### The definition that drives it — `I.Def45`, confirmed verbatim

star_health.pdf page 7, `SPECIFIC DEFINITIONS`, first entry:

> **Associated medical expenses:** Associated Medical Expenses means expenses
> that shall include the applicable nursing charges, Operation theatre charges,
> Professional fees of Medical Practitioner including Surgeon/ anaesthetist/
> Physician/Specialist of the Hospital where the Insured Person has been
> admitted and treated **and hence Proportionate deduction will be applicable
> on these items.**
>
> Associated Medical Expenses **does not include** cost of pharmacy and
> consumables, cost of implants and medical devices and cost of diagnostics,
> **ICU charges** and hence proportionate deduction will not be applicable on
> these items.

This settles the one thing worth checking hardest: **ICU is explicitly outside
Associated Medical Expenses in this policy**, so B01, B07, B19 and B33 paying
ICU in full is right, not an oversight. Same for medicines, consumables,
implants and diagnostics.

It also means citing `I.Def45` rather than `II.1` for the scaled lines is the
better citation, not a worse one — the definition itself carries the operative
words "hence Proportionate deduction will be applicable".

**B41 and B42** (Deluxe rooms at SI 10,00,000) are correctly left
`needs_human`. Page 8 defines Single Standard A/C Room as one that "does not
include a deluxe room or a suite", so the room does exceed entitlement — but
the policy states no rupee figure for that band, so it cannot be computed
without the schedule. Abstaining is right.

---

## Q3 — `hdfc_ergo` `B.1.1`, 20 rows — CORRECT

**What B.1.1 actually is** (hdfc_ergo.pdf, page 11, `SECTION B. BENEFITS` →
`1.1 Hospitalization Expenses`): room rent and boarding (a), ICU/ICCU (b),
surgeon, anaesthetist, practitioner, consultants, specialist fees (c),
investigations (d), medicines (e), consumables and OT charges (f), implanted
prosthetics (g); with road ambulance under 1.1.1.i.

The decisive sentence for these 20 rows is in (a):

> Room rent limit shall be **'At Actuals' unless otherwise specified in the
> Policy Schedule.**

So where `policy_schedule` is null — B02, B13, B20, B21, B24, B29, B35, B36,
B43 — the room is payable at actuals and **no proportionate deduction arises**.
Every one of those bills pays room and associated expenses in full. Correct.

Where a schedule exists, B.1.1.iii applies (page 12):

> Proportionate deduction on Room Rent: … the reimbursement/payment of Room Rent
> charges including all Associated Medical Expenses … shall be effected in the
> same proportion as the admissible rate per day bears to the actual rate per
> day … **Proportionate deduction will not apply for Associated Medical
> expenses incurred during the days Insured Person was admitted in ICU / ICCU.**

| bill | schedule | room | ratio | surgeon | key |
|---|---|---|---|---|---|
| B04 | 5,000/day | 9,500 × 7 → 35,000 | 0.526316 | 95,000 → 50,000.00 | ✓ |
| B15 | 6,000/day | 12,000 × 7 → 42,000 | 0.500000 | 110,000 → 55,000.00 | ✓ |
| B28 | 10,000/day | 22,000 × 8 → 80,000 | 0.454545 | 240,000 → 109,090.91 | ✓ |

ICU and ventilator charges paid in full in B15 and B28 — correct, per the
sentence above. Ambulance paid in full — hdfc states no rupee cap.

---

## Q4 — `niva_bupa` `6.2.4`, 12 rows — CORRECT

**What 6.2.4 actually is** (niva_bupa.pdf, page 25, `6.2 Specific Terms and
Clauses` → `6.2.4 Claims`). Sub-clause **d** is the operative rule:

> If you opt for a Hospital room which is higher than the eligible room category
> **as specified in your Policy Schedule**, then We will pay only a pro-rated
> portion of the total Associated Medical Expenses … as per the following
> formula:
>
> **(Eligible Room Rent limit / Room Rent actually incurred) × total Associated
> Medical Expenses**
>
> Associated Medical Expenses shall include **Room Rent, nursing charges,
> Medical Practitioners' fees and operation theatre charges.**

Note how much narrower niva's Associated Medical Expenses list is than
star_health's. Medicines and investigations are simply not in it, so they are
never scaled. The key reflects this correctly.

**B11** is the only Q4 bill with a schedule (6,000/day), and it reproduces exactly:

| line | charged | × 6,000/11,000 | key |
|---|---|---|---|
| Room Rent | 66,000 | 6,000 × 6 = 36,000 | 36,000 ✓ |
| Nursing | 12,000 | 6,545.45 | 6,545.45 ✓ |
| Surgeon | 88,000 | 48,000.00 | 48,000 ✓ |
| OT | 26,000 | 14,181.82 | 14,181.82 ✓ |
| Medicines | 34,000 | not in AME → full | 34,000 ✓ |
| Investigations | 18,000 | not in AME → full | 18,000 ✓ |

**B03, B06, B10** have no schedule. Because niva's entitlement is defined
*only* by the Policy Schedule, those room and AME lines are correctly returned
`needs_human` rather than guessed.

---

## Q5 — `star_health` `II.5`, 2 rows — CORRECT

**What II.5 actually is** (page 10): **Coverage for Modern Treatments**, a table
of per-treatment, per-policy-period limits by Sum Insured.

| bill | SI | treatment | table limit | charged | key |
|---|---|---|---|---|---|
| B12 | 500,000 | Robotic Assisted Surgery | 2,50,000 | 185,000 | 185,000 ✓ |
| B38 | 1,000,000 | Stem cell therapy, bone marrow transplant | 3,00,000 | 240,000 | 240,000 ✓ |

Both charges fall under their limit, so both are payable in full.

---

## Three things found while reading that are not part of the 72

**1. Each insurer derives the room entitlement from a different source, and the
key is right to treat them differently.**

| policy | entitlement comes from | when the Policy Schedule is blank |
|---|---|---|
| star_health | a Sum Insured table in II.1 | still computable — pay to the table |
| hdfc_ergo | the Schedule, else "At Actuals" | pay in full |
| niva_bupa | the Schedule only (6.2.4.d) | cannot be computed — needs_human |

This is why niva bills carry `needs_human` room lines and star_health bills do
not. It looks like an inconsistency in the key and is not one.

**2. "Ambulance" is item 67 on the IRDAI non-payable list, yet all three
policies cover road ambulance explicitly, and the key pays it.**

- star_health II.8 — capped at Rs 750 per hospitalization (B01: 1,000 → 750)
- hdfc_ergo 1.1.1.i — no rupee cap stated (B21: 1,800 → full; B28: 4,000 → full)
- niva_bupa — B10: 2,500 → full

If the audit pipeline has a non-payable fast path keyed on List I item names, it
will zero these lines and disagree with the key on every one. Worth checking
`core/` against `data/non_payable.json` entry 67 specifically. The same question
applies to entries 49 and 50, "Ambulance Collar" and "Ambulance Equipment",
which are genuinely non-payable and must stay so.

**3. A convention slip in the key, cosmetic but worth tidying.**

`answer_key.json`'s own instructions say: *"When needs_human is true, leave
allowed and clause_id as null."* Several niva_bupa rows (B03, B06, B10) have
`allowed: null` while still carrying `clause_id: "6.2.4"`. The information is
useful — it names the clause that *would* decide once a schedule exists — but it
departs from the stated rule, and any metric that measures citation accuracy
over abstained rows will pick it up. Decide which convention you want and make
the file consistent with it.
