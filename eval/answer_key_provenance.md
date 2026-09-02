# How the answer key was derived

## Method

Every figure in `eval/answer_key.json` was derived by reading the three policy
PDFs directly with `pdfplumber`, page by page, both columns, at full page
context. The derivation is scripted in `eval/derive_key.py` so it is
reproducible and auditable: each line carries a `derivation` string quoting the
policy sentence and showing the arithmetic.

```
"II.1 p10 table: Sum Insured 300,000 -> Up to 5,000/- per day;
 5,000 x 5 = 25,000, min(40,000, 25,000) = 25,000"
```

**Nothing here ran the pipeline.** `derive_key.py` imports no retriever, no
judge and no audit code. It reads the PDFs on a different path from ingestion —
whole pages rather than split clauses — so a splitter bug cannot propagate into
the key and then be scored as a success.

## The limit of that independence

This key was written by a language model reading policy documents. The judge in
the pipeline is also a language model reading policy documents. Reading full
pages by a different route removes the shared *plumbing*, but not the shared
*reader*. A misreading available to one is available to the other.

That is why the ten bills listed at the end need checking by a person. Until
they are checked, treat the accuracy numbers as provisional.

**The evidence for that check is laid out in
[`answer_key_review.md`](answer_key_review.md)** - every line of those bills
beside the clause it cites, quoted verbatim, with the page it was located on and
the arithmetic written out, and a CONFIRMED column to sign. Regenerate it with
`uv run python eval/build_answer_key_review.py`. It prepares the check; it does
not perform it, and it changes nothing in `answer_key.json`.

## Rules read from the documents

### Star Health — Family Health Optima

| rule | source | value |
|---|---|---|
| Room rent | II.1, p10 table | 1L/2L → Rs 2,000/day · 3L/4L → Rs 5,000/day · **5L and above → "Single Standard A/C Room", a category with no rupee cap** |
| Proportionate deduction | II.1 Note, p10 | associated medical expenses reduced in proportion to the eligible room rent |
| Associated Medical Expenses | I.Def45, p8 | **includes** nursing, operation theatre, practitioners' fees · **excludes** pharmacy and consumables, implants and devices, diagnostics, **and ICU charges** |
| Cataract | II.3, p10 table | 3L → 25,000/eye · 4L → 30,000 · 5L → 40,000 · 10L+ → 50,000 |
| Modern treatments | II.5, p11 table | robotic surgery by sum insured; 5L → 2,50,000, 10L → 3,00,000 |
| Road ambulance | II.8, p12 | Rs 750 per hospitalisation and Rs 1,500 per policy period |
| Registration/admission | III.31, p32 | excluded, Code Excl 34 |
| Co-payment | II.28, p21 | 20%, but only where entry age is 61 or above |
| Specified disease wait | III.2, p28-29 | 24 months; list includes cataract, hernia, joint replacement, uterine/cervical conditions, haemorrhoids/fissure/fistula |

### HDFC Ergo — Optima Secure

| rule | source | value |
|---|---|---|
| Room rent and ICU | B.1.1, p11 | **"At Actuals unless otherwise specified in the Policy Schedule"** |
| Proportionate deduction | B.1.1.1, p11 | applies where the room exceeds the schedule's category/limit; **not applicable to ICU charges** |
| Associated Medical Expenses | A.1.2.Def5, p8 | consultation fees, operation theatre, surgical appliances and nursing, anaesthesia/blood/oxygen; **excludes** pharmacy and consumables, implants and devices, diagnostics |
| AYUSH | B.1.4, p12 | "up to the Sub-limit specified against this Cover in the Policy Schedule" — **no figure in the wording** |
| Specified disease wait | C.1, p28 | 24 months |

### Niva Bupa — ReAssure 2.0

| rule | source | value |
|---|---|---|
| Room rent | 6.2.4, p26 | pro-rata where the room is "higher than the eligible room category as specified in your Policy Schedule" |
| Formula | 6.2.4, p26 | `(Eligible Room Rent limit / Room Rent actually incurred) x total Associated Medical Expenses` |
| Associated Medical Expenses | 6.2.4, p26 | room rent, nursing charges, practitioners' fees, operation theatre charges |
| Specified disease wait | 5.1.2, p15 | 24 months; list includes cataract, hysterectomy, haemorrhoids/fissure/fistula, hernia, joint replacement |

## Judgement calls I had to make

These are decisions, not readings. Each could reasonably go the other way.

**1. Co-payment is not applied anywhere.** Star Health's 20% co-payment applies
only to insured persons "whose age at the time of entry is 61 years and above".
No bill states an age, so no co-payment is applied. If you intend the eval to
exercise co-payment, the bills need an age field.

**2. A waiting-period breach voids the entire admission.** The wording excludes
"expenses related to the treatment of the listed conditions". Room rent and
medicines for that admission are related to that treatment, so all five
waiting-period bills come out at nil throughout, not just the surgery line.

**3. ICU is never proportionately reduced.** All three policies place ICU
outside associated medical expenses. Star Health and HDFC say so explicitly.
This materially raises the payable figure on every room-rent-over bill.

**4. Medicines, diagnostics and implants are never proportionately reduced.**
Same basis — all three policies exclude them from associated medical expenses.

**5. Syringes are payable; gloves are not.** "Gloves" is IRDAI List I #56.
Disposable syringes appear nowhere on the list, so they are treated as a
payable treatment consumable. This is the closest call in the key.

**6. "Ambulance" on the IRDAI list does not override an ambulance benefit.**
List I #67 is "Ambulance", but Star Health II.8 is a named ambulance benefit.
The benefit clause wins; the list entry is read as covering ambulance equipment
billed as an item. For HDFC and Niva, which have no matching benefit clause in
the retrieved wording, ambulance is currently paid in full — **this is weak.**

## Where the key contradicts the bills' own design

**B43 now comes back fully answered, and it was built to abstain.**

The design intent was that HDFC with no policy schedule cannot decide a room
limit, so the line should return `needs_human`. But the wording states a
default: *"Room rent limit shall be 'At Actuals' unless otherwise specified in
the Policy Schedule."* Absent a schedule, At Actuals **is** what the policy
says applies. That is a decision, not a gap, so the key pays it in full.

Niva Bupa states no such default, so B44 does abstain. The asymmetry is real
and comes from the documents, not from a preference.

This leaves a conflict to resolve:

- If the **product rule** stands (blank schedule → always abstain), the key is wrong for B43 and the audit code is right.
- If the **document** stands (At Actuals is a stated default), the key is right and `SCHEDULE_DEFERRAL_RE` in `core/audit.py` over-fires on HDFC.

I have followed the document, because the instruction was not to invent a gap
where the policy decides. **This needs your decision before the numbers mean
anything.**

## Entries I am least confident in

| bill | line | why |
|---|---|---|
| B38 | Stem Cell Therapy 2,40,000 | II.5 is a six-column grid. I applied the **robotic surgery** column. Stem cell is a different column and at least one row reads "Up to Sum Insured". Likely wrong. |
| B03, B31 | Cataract on Niva Bupa | I found no cataract sub-limit in the Niva wording, so both are paid in full. Star Health has an explicit table; it would be surprising if Niva had none. |
| B21, B39 | "Ambulance" line on HDFC and Niva | Paid in full with no benefit clause located. Either there is an ambulance sub-limit I did not find, or the IRDAI list entry should exclude it. |
| B24 | AYUSH on HDFC | Flagged `needs_human` because the wording defers the sub-limit to the schedule. Correct by the document, but it makes a "sub_limit" bill untestable. |
| B41, B42 | Star Health Deluxe room at 10L | Flagged. The policy grants "Single Standard A/C Room"; a Deluxe room exceeds it but no rupee limit exists to build a ratio from. |
| all | Physiotherapy lines | Flagged in B04, B11, B19, B33. No clause in any policy states a limit for physiotherapy billed as a separate line. |
| all | Consultant visit charges | Treated as an associated medical expense and therefore proportionately reduced. Defensible under "Professional fees of Medical Practitioner", but not certain. |

## Summary

- 330 lines across 44 bills
- **303 answered**, **27 flagged** `needs_human`
- 33 bills fully answered, 11 carrying at least one flagged line
- Every answered line carries a quoted derivation
