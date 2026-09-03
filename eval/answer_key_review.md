# Answer key review — evidence for a human check

`eval/answer_key_provenance.md` records that this key was written by a language
model reading the policy PDFs, that the judge in the pipeline is also a language
model reading the policy PDFs, and that **until a person checks the
least-confident bills the accuracy numbers are provisional**. This file is that
check laid out, not that check performed.

**Nothing here decides whether an entry is right.** Every row carries the bill
line, what the key claims, the clause it cites quoted verbatim from
`data/clauses.json`, the page of the source PDF that text was located on, and
the arithmetic — then two empty columns for you. Rows the evidence does not
support are listed under **CANNOT SUPPORT** below rather than corrected.

**93 rows across 13 bills.** Sign off in the
CONFIRMED column: `y` if the PDF bears the entry out, `n` if it does not.

## Which bills these are

`answer_key_provenance.md` says "the ten bills listed at the end", but the table
at its end names **eight** in the bill column (B38, B03, B31, B21, B39, B24, B41,
B42) and **four more** inside the why column of its physiotherapy row (B04, B11,
B19, B33). B43 is not in that table at all but has its own section ending "this
needs your decision before the numbers mean anything".

Eight, twelve or thirteen is your call to make, not this script's, so **all
thirteen are here** — a superset cannot be wrong by omission. Where a bill sits:

| Bill | Why it is in scope |
|---|---|
| B03 | named in the bill column of *Entries I am least confident in* |
| B04 | named in the why column of the physiotherapy row |
| B11 | named in the why column of the physiotherapy row |
| B19 | named in the why column of the physiotherapy row |
| B21 | named in the bill column of *Entries I am least confident in* |
| B24 | named in the bill column of *Entries I am least confident in* |
| B31 | named in the bill column of *Entries I am least confident in* |
| B33 | named in the why column of the physiotherapy row |
| B38 | named in the bill column of *Entries I am least confident in* |
| B39 | named in the bill column of *Entries I am least confident in* |
| B41 | named in the bill column of *Entries I am least confident in* |
| B42 | named in the bill column of *Entries I am least confident in* |
| B43 | *Where the key contradicts the bills' own design* — B43 needs a decision |

## CANNOT SUPPORT

Entries whose cited clause does not exist, does not contain what the key says it
does, or does not establish what the key concludes from it. **Not corrected, not
adjusted — reported.** Each is a question for you, not a verdict from me.

### B03 (niva_bupa)

- **Room Rent (Shared) 2,500 x 1 day** — cites `6.2.4`
  - the derivation itself says no clause was located, yet the row is answered rather than flagged: 'no default stated'

### B04 (hdfc_ergo)

- **Nursing Charges** — cites `B.1.1.1`
  - the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']
- **Surgeon Fee** — cites `B.1.1.1`
  - the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']
- **Assistant Surgeon Fee** — cites `B.1.1.1`
  - the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']
- **Medicines and Drugs** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id
- **Operation Theatre Charges** — cites `B.1.1.1`
  - the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']
- **Investigations - MRI** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

### B19 (star_health)

- **Room Rent (Suite) 15,000 x 7 days** — cites `II.1`
  - the derivation says p10; the quoted text is on p9
- **ICU Charges 20,000 x 2 days** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Surgeon Fee** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
- **Anaesthetist Charges** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
- **Medicines and Drugs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Operation Theatre Charges** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
- **Investigations - PET CT** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

### B21 (hdfc_ergo)

- **Medicines and Drugs** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id
- **Ambulance** — cites `B.1.1`
  - the derivation itself says no clause was located, yet the row is answered rather than flagged: 'no specific limit found'
- **Investigations - Labs** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

### B24 (hdfc_ergo)

- **Medicines - Ayurvedic Preparations** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id
- **Investigations - Basic Panel** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

### B31 (niva_bupa)

- **Room Rent (Shared) 2,500 x 1 day** — cites `6.2.4`
  - the derivation itself says no clause was located, yet the row is answered rather than flagged: 'no default stated'

### B33 (star_health)

- **Room Rent (Suite) 18,000 x 6 days** — cites `II.1`
  - the derivation says p10; the quoted text is on p9
- **ICU Charges 24,000 x 2 days** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Surgeon Fee** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
- **Anaesthetist Charges** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
- **Medicines and Drugs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Operation Theatre Charges** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
- **Investigations - CT, MRI, Labs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

### B38 (star_health)

- **Stem Cell Therapy for Bone Marrow Transplant** — cites `II.5`
  - 18 data cells in this clause's table hold column headings instead of figures (1,00,000/- column 4, 1,00,000/- column 5, 2,00,000/- column 4...), so the columns do not line up and a figure read out of the index may belong to a different treatment. Read the grid on the PDF page directly
- **Medicines and Drugs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Investigations - Pre-procedure Panel** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

### B41 (star_health)

- **ICU Charges 16,000 x 2 days** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Medicines and Drugs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Investigations - CT and Labs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

### B42 (star_health)

- **Medicines and Drugs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id
- **Investigations - MRI and Labs** — cites `II.1`
  - the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']
  - clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

### B43 (hdfc_ergo)

- **Medicines - Ayurvedic Preparations** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id
- **Investigations - Basic Panel** — cites `B.1.1`
  - the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']
  - clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

**37 rows flagged.**

## B03

| | |
|---|---|
| Policy | niva_bupa |
| Sum insured | Rs 500,000 |
| Policy start date | 2020-11-20 |
| Admission date | 2026-01-14 |
| Policy schedule | none supplied |
| Category | sub_limit |
| Total charged | Rs 116,500 |
| Key total payable | Rs 116,500 |

### B03.1 — Room Rent (Shared) 2,500 x 1 day

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Shared) 2,500 x 1 day                1     2,500.00` |
| Key says payable | Rs 2,500 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: pro-rata applies to a room "higher than the eligible room category as specified in your Policy Schedule" - no schedule supplied and no default stated; a shared room is the lowest category and cannot exceed any entitlement; charge is within entitlement -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation itself says no clause was located, yet the row is answered rather than flagged: 'no default stated'

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B03.2 — Cataract Surgery - Right Eye Package

| Field | Value |
|---|---|
| Bill line, as printed | `Cataract Surgery - Right Eye Package            1    68,000.00` |
| Key says payable | Rs 68,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B03.3 — Intraocular Lens

| Field | Value |
|---|---|
| Bill line, as printed | `Intraocular Lens                                1    22,000.00` |
| Key says payable | Rs 22,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B03.4 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1    18,000.00` |
| Key says payable | Rs 18,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p25 (index records p25) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Cashless claim facility is available at our network hospitals ONLY.
```

Arithmetic, as the key records it:

```
room rent within the eligible limit, so no proportionate deduction -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B03.5 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1     3,200.00` |
| Key says payable | Rs 3,200 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B03.6 — Pre-operative Investigations

| Field | Value |
|---|---|
| Bill line, as printed | `Pre-operative Investigations                    1     2,800.00` |
| Key says payable | Rs 2,800 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B04

| | |
|---|---|
| Policy | hdfc_ergo |
| Sum insured | Rs 300,000 |
| Policy start date | 2023-01-10 |
| Admission date | 2026-04-02 |
| Policy schedule | {"room_limit_per_day": 5000.0, "room_category": null} |
| Category | room_rent_over |
| Total charged | Rs 290,500 |
| Key total payable | Rs 175,316 |

### B04.1 — Room Rent (Single A/C) 9,500 x 7 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Single A/C) 9,500 x 7 days           7    66,500.00` |
| Key says payable | Rs 35,000 |
| Deduction | Rs 31,500 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Hospitalization Expenses
The Company shall indemnify Medical Expenses necessarily incurred by the Insured Person for Hospitalization of the Insured Person during the Policy Year due to Illness or Injury, up to the Sum Insured specified in the Policy Schedule for:
a.
```

Arithmetic, as the key records it:

```
policy schedule states room limit Rs 5,000 per day; 5,000 x 7 = 35,000, min(66,500, 35,000) = 35,000
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B04.2 — Nursing Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Nursing Charges                                 7    14,000.00` |
| Key says payable | Rs 7,368 |
| Deduction | Rs 6,632 |
| clause_id | `B.1.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Expenses incurred on road Ambulance if the Insured Person is required to be transferred to the nearest Hospital for Emergency Care or from one Hospital to another Hospital or from Hospital to Home (within same city) following Hospitalization.
```

Arithmetic, as the key records it:

```
B.1.1.1: room rent 9,500/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/9,500 = 0.5263; A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; 14,000 x 0.5263 = 7,368.42
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B04.3 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1    95,000.00` |
| Key says payable | Rs 50,000 |
| Deduction | Rs 45,000 |
| clause_id | `B.1.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Expenses incurred on road Ambulance if the Insured Person is required to be transferred to the nearest Hospital for Emergency Care or from one Hospital to another Hospital or from Hospital to Home (within same city) following Hospitalization.
```

Arithmetic, as the key records it:

```
B.1.1.1: room rent 9,500/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/9,500 = 0.5263; A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; 95,000 x 0.5263 = 50,000.00
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B04.4 — Assistant Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Assistant Surgeon Fee                           1    25,000.00` |
| Key says payable | Rs 13,158 |
| Deduction | Rs 11,842 |
| clause_id | `B.1.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Expenses incurred on road Ambulance if the Insured Person is required to be transferred to the nearest Hospital for Emergency Care or from one Hospital to another Hospital or from Hospital to Home (within same city) following Hospitalization.
```

Arithmetic, as the key records it:

```
B.1.1.1: room rent 9,500/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/9,500 = 0.5263; A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; 25,000 x 0.5263 = 13,157.89
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B04.5 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    42,000.00` |
| Key says payable | Rs 42,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B04.6 — Operation Theatre Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Operation Theatre Charges                       1    30,000.00` |
| Key says payable | Rs 15,789 |
| Deduction | Rs 14,211 |
| clause_id | `B.1.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Expenses incurred on road Ambulance if the Insured Person is required to be transferred to the nearest Hospital for Emergency Care or from one Hospital to another Hospital or from Hospital to Home (within same city) following Hospitalization.
```

Arithmetic, as the key records it:

```
B.1.1.1: room rent 9,500/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/9,500 = 0.5263; A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; 30,000 x 0.5263 = 15,789.47
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1.1 does not contain - it is in ['A.1.2.Def5']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B04.7 — Physiotherapy Sessions

| Field | Value |
|---|---|
| Bill line, as printed | `Physiotherapy Sessions                          4     6,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `None` |
| Located in the PDF on | **NOT FOUND** |
| Why this text | no clause body to quote |

Clause text, verbatim from `data/clauses.json`:

```
NOT FOUND
```

Arithmetic, as the key records it:

```
no clause in this policy states a limit for physiotherapy as a separate billed line
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B04.8 — Investigations - MRI

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - MRI                            1    12,000.00` |
| Key says payable | Rs 12,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B11

| | |
|---|---|
| Policy | niva_bupa |
| Sum insured | Rs 300,000 |
| Policy start date | 2022-12-05 |
| Admission date | 2026-04-11 |
| Policy schedule | {"room_limit_per_day": 6000.0, "room_category": null} |
| Category | room_rent_over |
| Total charged | Rs 249,000 |
| Key total payable | Rs 156,727 |

### B11.1 — Room Rent (Single Private) 11,000 x 6 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Single Private) 11,000 x 6 days      6    66,000.00` |
| Key says payable | Rs 36,000 |
| Deduction | Rs 30,000 |
| clause_id | `6.2.4` |
| Located in the PDF on | p25 (index records p25) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Cashless claim facility is available at our network hospitals ONLY.
```

Arithmetic, as the key records it:

```
policy schedule states room limit Rs 6,000 per day; 6,000 x 6 = 36,000, min(66,000, 36,000) = 36,000
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B11.2 — Nursing Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Nursing Charges                                 6    12,000.00` |
| Key says payable | Rs 6,545 |
| Deduction | Rs 5,455 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4: room rent 11,000/day exceeds the eligible 6,000/day, so associated medical expenses are reduced in the same proportion: 6,000/11,000 = 0.5455; 6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; 12,000 x 0.5455 = 6,545.45
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B11.3 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1    88,000.00` |
| Key says payable | Rs 48,000 |
| Deduction | Rs 40,000 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4: room rent 11,000/day exceeds the eligible 6,000/day, so associated medical expenses are reduced in the same proportion: 6,000/11,000 = 0.5455; 6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; 88,000 x 0.5455 = 48,000.00
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B11.4 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    34,000.00` |
| Key says payable | Rs 34,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B11.5 — Operation Theatre Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Operation Theatre Charges                       1    26,000.00` |
| Key says payable | Rs 14,182 |
| Deduction | Rs 11,818 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4: room rent 11,000/day exceeds the eligible 6,000/day, so associated medical expenses are reduced in the same proportion: 6,000/11,000 = 0.5455; 6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; 26,000 x 0.5455 = 14,181.82
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B11.6 — Investigations - MRI and Labs

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - MRI and Labs                   1    18,000.00` |
| Key says payable | Rs 18,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B11.7 — Physiotherapy Sessions

| Field | Value |
|---|---|
| Bill line, as printed | `Physiotherapy Sessions                          3     5,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `None` |
| Located in the PDF on | **NOT FOUND** |
| Why this text | no clause body to quote |

Clause text, verbatim from `data/clauses.json`:

```
NOT FOUND
```

Arithmetic, as the key records it:

```
no clause in this policy states a limit for physiotherapy as a separate billed line
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B19

| | |
|---|---|
| Policy | star_health |
| Sum insured | Rs 400,000 |
| Policy start date | 2021-06-03 |
| Admission date | 2026-04-05 |
| Policy schedule | none supplied |
| Category | room_rent_over |
| Total charged | Rs 520,000 |
| Key total payable | Rs 271,750 |

### B19.1 — Room Rent (Suite) 15,000 x 7 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Suite) 15,000 x 7 days               7   105,000.00` |
| Key says payable | Rs 35,000 |
| Deduction | Rs 70,000 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1 p10 table: Sum Insured 400,000 -> Up to 5,000/- per day; 5,000 x 7 = 35,000, min(105,000, 35,000) = 35,000
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation says p10; the quoted text is on p9

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.2 — ICU Charges 20,000 x 2 days

| Field | Value |
|---|---|
| Bill line, as printed | `ICU Charges 20,000 x 2 days                     2    40,000.00` |
| Key says payable | Rs 40,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; ICU is outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 3: ICU is never proportionately reduced (all three policies place it outside AME)**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.3 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1   165,000.00` |
| Key says payable | Rs 55,000 |
| Deduction | Rs 110,000 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1: room rent 15,000/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/15,000 = 0.3333; I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; 165,000 x 0.3333 = 55,000.00
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.4 — Anaesthetist Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Anaesthetist Charges                            1    35,000.00` |
| Key says payable | Rs 11,667 |
| Deduction | Rs 23,333 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1: room rent 15,000/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/15,000 = 0.3333; I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; 35,000 x 0.3333 = 11,666.67
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.5 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    78,000.00` |
| Key says payable | Rs 78,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.6 — Operation Theatre Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Operation Theatre Charges                       1    52,000.00` |
| Key says payable | Rs 17,333 |
| Deduction | Rs 34,667 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1: room rent 15,000/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/15,000 = 0.3333; I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; 52,000 x 0.3333 = 17,333.33
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.7 — Investigations - PET CT

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - PET CT                         1    34,000.00` |
| Key says payable | Rs 34,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.8 — Physiotherapy Sessions

| Field | Value |
|---|---|
| Bill line, as printed | `Physiotherapy Sessions                          4     8,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `None` |
| Located in the PDF on | **NOT FOUND** |
| Why this text | no clause body to quote |

Clause text, verbatim from `data/clauses.json`:

```
NOT FOUND
```

Arithmetic, as the key records it:

```
no clause in this policy states a limit for physiotherapy as a separate billed line
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B19.9 — Ambulance Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Ambulance Charges                               1     3,000.00` |
| Key says payable | Rs 750 |
| Deduction | Rs 2,250 |
| clause_id | `II.8` |
| Located in the PDF on | p12 (index records p12) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
Road ambulance: Subject to an admissible
hospitalization claim, road ambulance expenses up to Rs.750/- per hospitalization and up to Rs.1,500/- per Policy Period shall be payable for the following:
i.
```

Arithmetic, as the key records it:

```
II.8 p12: "road ambulance expenses up to Rs.750/- per hospitalization"; min(3,000, 750) = 750
```

> **ASSUMPTION 6: an IRDAI 'Ambulance' list entry does not override a named ambulance benefit**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B21

| | |
|---|---|
| Policy | hdfc_ergo |
| Sum insured | Rs 300,000 |
| Policy start date | 2023-02-09 |
| Admission date | 2026-02-27 |
| Policy schedule | none supplied |
| Category | non_payable |
| Total charged | Rs 77,950 |
| Key total payable | Rs 74,800 |

### B21.1 — Room Rent (Shared) 2,800 x 3 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Shared) 2,800 x 3 days               3     8,400.00` |
| Key says payable | Rs 8,400 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
Room rent limit shall be ‘At Actuals’ unless otherwise specified in the Policy Schedule.
```

Arithmetic, as the key records it:

```
B.1.1 p11: "Room rent limit shall be 'At Actuals' unless otherwise specified in the Policy Schedule"; no schedule supplied, so At Actuals applies; charge is within entitlement -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.2 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1    44,000.00` |
| Key says payable | Rs 44,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Hospitalization Expenses
The Company shall indemnify Medical Expenses necessarily incurred by the Insured Person for Hospitalization of the Insured Person during the Policy Year due to Illness or Injury, up to the Sum Insured specified in the Policy Schedule for:
a.
```

Arithmetic, as the key records it:

```
room rent within the eligible limit, so no proportionate deduction -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.3 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    16,000.00` |
| Key says payable | Rs 16,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.4 — Gloves

| Field | Value |
|---|---|
| Bill line, as printed | `Gloves                                         18     1,000.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 1,000 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in hdfc_ergo.pdf p49 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 56: Gloves
```

Arithmetic, as the key records it:

```
IRDAI-List-I #56 "gloves" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.5 — Kidney Tray

| Field | Value |
|---|---|
| Bill line, as printed | `Kidney Tray                                     2       250.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 250 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in hdfc_ergo.pdf p50 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 59: Kidney Tray
```

Arithmetic, as the key records it:

```
IRDAI-List-I #59 "kidney tray" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.6 — Urometer, Urine Jug

| Field | Value |
|---|---|
| Bill line, as printed | `Urometer, Urine Jug                             1       600.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 600 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in hdfc_ergo.pdf p50 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 66: Urometer, Urine Jug
```

Arithmetic, as the key records it:

```
IRDAI-List-I #66 "urometer, urine jug" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.7 — Vasofix Safety

| Field | Value |
|---|---|
| Bill line, as printed | `Vasofix Safety                                  4       400.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 400 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in hdfc_ergo.pdf p50 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 68: Vasofix Safety
```

Arithmetic, as the key records it:

```
IRDAI-List-I #68 "vasofix safety" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.8 — Ambulance

| Field | Value |
|---|---|
| Bill line, as printed | `Ambulance                                       1     1,800.00` |
| Key says payable | Rs 1,800 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Hospitalization Expenses
The Company shall indemnify Medical Expenses necessarily incurred by the Insured Person for Hospitalization of the Insured Person during the Policy Year due to Illness or Injury, up to the Sum Insured specified in the Policy Schedule for:
a.
```

Arithmetic, as the key records it:

```
no specific limit found for this item; covered as a hospitalization expense -> paid in full
```

> **ASSUMPTION 6: an IRDAI 'Ambulance' list entry does not override a named ambulance benefit**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation itself says no clause was located, yet the row is answered rather than flagged: 'no specific limit found'

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.9 — Food Charges (other than patient's diet provided by hospital)

| Field | Value |
|---|---|
| Bill line, as printed | `Food Charges (other than patient's diet prov    1       900.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 900 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in hdfc_ergo.pdf p32 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 9: Food Charges (other than patient’s diet provided by hospital)
```

Arithmetic, as the key records it:

```
IRDAI-List-I #9 "food charges" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B21.10 — Investigations - Labs

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - Labs                           1     4,600.00` |
| Key says payable | Rs 4,600 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B24

| | |
|---|---|
| Policy | hdfc_ergo |
| Sum insured | Rs 500,000 |
| Policy start date | 2019-04-08 |
| Admission date | 2026-02-06 |
| Policy schedule | none supplied |
| Category | sub_limit |
| Total charged | Rs 112,600 |
| Key total payable | Rs 20,600 |

### B24.1 — Room Rent (Shared) 3,000 x 1 day

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Shared) 3,000 x 1 day                1     3,000.00` |
| Key says payable | Rs 3,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
Room rent limit shall be ‘At Actuals’ unless otherwise specified in the Policy Schedule.
```

Arithmetic, as the key records it:

```
B.1.1 p11: "Room rent limit shall be 'At Actuals' unless otherwise specified in the Policy Schedule"; no schedule supplied, so At Actuals applies; charge is within entitlement -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B24.2 — AYUSH Inpatient Treatment Package

| Field | Value |
|---|---|
| Bill line, as printed | `AYUSH Inpatient Treatment Package               1    92,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `None` |
| Located in the PDF on | p12 |
| Why this text | the sentence the key's derivation quotes, from B.1.4 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
AYUSH Treatment
The Company shall indemnify the Medical Expenses incurred by the Insured Person only for Inpatient Care under Ayurveda, Yoga and Naturopathy, Unani, Siddha and Homeopathy systems of medicines during each Policy Year up to the Sub-limit specified against this Cover in the Policy Schedule, in any AYUSH Hospital.
```

Arithmetic, as the key records it:

```
B.1.4 p12: AYUSH is payable "up to the Sub-limit specified against this Cover in the Policy Schedule" - the wording states no figure and no schedule was supplied
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B24.3 — Consultant Visit Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Consultant Visit Charges                        2     4,000.00` |
| Key says payable | Rs 4,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Hospitalization Expenses
The Company shall indemnify Medical Expenses necessarily incurred by the Insured Person for Hospitalization of the Insured Person during the Policy Year due to Illness or Injury, up to the Sum Insured specified in the Policy Schedule for:
a.
```

Arithmetic, as the key records it:

```
room rent within the eligible limit, so no proportionate deduction -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B24.4 — Medicines - Ayurvedic Preparations

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines - Ayurvedic Preparations              1    11,000.00` |
| Key says payable | Rs 11,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B24.5 — Investigations - Basic Panel

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - Basic Panel                    1     2,600.00` |
| Key says payable | Rs 2,600 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B31

| | |
|---|---|
| Policy | niva_bupa |
| Sum insured | Rs 300,000 |
| Policy start date | 2020-06-07 |
| Admission date | 2026-04-19 |
| Policy schedule | none supplied |
| Category | sub_limit |
| Total charged | Rs 103,300 |
| Key total payable | Rs 103,300 |

### B31.1 — Room Rent (Shared) 2,500 x 1 day

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Shared) 2,500 x 1 day                1     2,500.00` |
| Key says payable | Rs 2,500 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: pro-rata applies to a room "higher than the eligible room category as specified in your Policy Schedule" - no schedule supplied and no default stated; a shared room is the lowest category and cannot exceed any entitlement; charge is within entitlement -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation itself says no clause was located, yet the row is answered rather than flagged: 'no default stated'

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B31.2 — Cataract Surgery - Right Eye

| Field | Value |
|---|---|
| Bill line, as printed | `Cataract Surgery - Right Eye                    1    62,000.00` |
| Key says payable | Rs 62,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B31.3 — Intraocular Lens - Premium

| Field | Value |
|---|---|
| Bill line, as printed | `Intraocular Lens - Premium                      1    34,000.00` |
| Key says payable | Rs 34,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B31.4 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1     2,600.00` |
| Key says payable | Rs 2,600 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B31.5 — Pre-operative Investigations

| Field | Value |
|---|---|
| Bill line, as printed | `Pre-operative Investigations                    1     2,200.00` |
| Key says payable | Rs 2,200 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B33

| | |
|---|---|
| Policy | star_health |
| Sum insured | Rs 400,000 |
| Policy start date | 2020-04-23 |
| Admission date | 2026-03-02 |
| Policy schedule | none supplied |
| Category | room_rent_over |
| Total charged | Rs 582,000 |
| Key total payable | Rs 283,389 |

### B33.1 — Room Rent (Suite) 18,000 x 6 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Suite) 18,000 x 6 days               6   108,000.00` |
| Key says payable | Rs 30,000 |
| Deduction | Rs 78,000 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1 p10 table: Sum Insured 400,000 -> Up to 5,000/- per day; 5,000 x 6 = 30,000, min(108,000, 30,000) = 30,000
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation says p10; the quoted text is on p9

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B33.2 — ICU Charges 24,000 x 2 days

| Field | Value |
|---|---|
| Bill line, as printed | `ICU Charges 24,000 x 2 days                     2    48,000.00` |
| Key says payable | Rs 48,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; ICU is outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 3: ICU is never proportionately reduced (all three policies place it outside AME)**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B33.3 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1   195,000.00` |
| Key says payable | Rs 54,167 |
| Deduction | Rs 140,833 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1: room rent 18,000/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/18,000 = 0.2778; I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; 195,000 x 0.2778 = 54,166.67
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B33.4 — Anaesthetist Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Anaesthetist Charges                            1    40,000.00` |
| Key says payable | Rs 11,111 |
| Deduction | Rs 28,889 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1: room rent 18,000/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/18,000 = 0.2778; I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; 40,000 x 0.2778 = 11,111.11
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B33.5 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    86,000.00` |
| Key says payable | Rs 86,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B33.6 — Operation Theatre Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Operation Theatre Charges                       1    58,000.00` |
| Key says payable | Rs 16,111 |
| Deduction | Rs 41,889 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
II.1: room rent 18,000/day exceeds the eligible 5,000/day, so associated medical expenses are reduced in the same proportion: 5,000/18,000 = 0.2778; I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; 58,000 x 0.2778 = 16,111.11
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B33.7 — Investigations - CT, MRI, Labs

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - CT, MRI, Labs                  1    38,000.00` |
| Key says payable | Rs 38,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B33.8 — Physiotherapy Sessions

| Field | Value |
|---|---|
| Bill line, as printed | `Physiotherapy Sessions                          5     9,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `None` |
| Located in the PDF on | **NOT FOUND** |
| Why this text | no clause body to quote |

Clause text, verbatim from `data/clauses.json`:

```
NOT FOUND
```

Arithmetic, as the key records it:

```
no clause in this policy states a limit for physiotherapy as a separate billed line
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B38

| | |
|---|---|
| Policy | star_health |
| Sum insured | Rs 1,000,000 |
| Policy start date | 2020-01-08 |
| Admission date | 2026-04-01 |
| Policy schedule | none supplied |
| Category | sub_limit |
| Total charged | Rs 334,000 |
| Key total payable | Rs 334,000 |

### B38.1 — Room Rent (Shared) 3,500 x 1 day

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Shared) 3,500 x 1 day                1     3,500.00` |
| Key says payable | Rs 3,500 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
II.1 p10 table: Sum Insured 1,000,000 -> "Single Standard A/C Room" - a room category, no rupee limit stated; the room occupied (Shared) 3,500 x 1 day) is at or below that category, so nothing is deducted; charge is within entitlement -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B38.2 — Stem Cell Therapy for Bone Marrow Transplant

| Field | Value |
|---|---|
| Bill line, as printed | `Stem Cell Therapy for Bone Marrow Transplant    1   240,000.00` |
| Key says payable | Rs 240,000 |
| Deduction | Rs 0 |
| clause_id | `II.5` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | every heading in this clause's table(s), and every data row for sum insured 10,00,000 - read the columns across |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) - Uterine artery Embolization and HIFU - Balloon Sinuplasty - Deep Brain Stimulation - Oral Chemotherapy* (Sublimits including Pre and Post Hospitalization) - Immunotheraphy- Monoclonal Antibody to be given as injection - Intra Vitreal injections
[table] Sum Insured (Rs.) - Limit per Policy Period for each treatment/procedure (Rs.) - Balloon Sinuplasty - Deep Brain Stimulation - Oral Chemotherapy* (Sublimits including Pre and Post Hospitalization) - Immunotheraphy- Monoclonal Antibody to be given as injection - Intra Vitreal injections
[table] * Sublimits are all inclusive with or without hospitalization wherever hospitalization includes pre and post hospitalization. - 2,00,000/- - 1,50,000/- - 5,00,000/- - 3,00,000/- - 6,00,000/- - 1,50,000/-
[table] Sum Insured (Rs.) - Robotic surgeries - Stereotactic radio surgeries - Bronchical Thermoplasty - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - Stem cell therapy: Hematopoietic stem cells for bone marrow transplant for haematological conditions
[table] Sum Insured (Rs.) - Limit per Policy Period for each treatment/procedure (Rs.) - Stereotactic radio surgeries - Bronchical Thermoplasty - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - Stem cell therapy: Hematopoietic stem cells for bone marrow transplant for haematological conditions
[table] 10,00,000/- - 1,50,000/- - 1,00,000/- - 3,00,000/- - 2,00,000/- - 4,00,000/- - 75,000/-
[table] 10,00,000/- - 3,00,000/- - 2,25,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 3,00,000/-
```

Arithmetic, as the key records it:

```
II.5 p11 table: Sum Insured 1,000,000 -> Up to 300,000/- per treatment per policy period; min(240,000, 300,000) = 240,000
```

> **Coverage check.** Paid in full. The only clause cited is `II.5`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** 18 data cells in this clause's table hold column headings instead of figures (1,00,000/- column 4, 1,00,000/- column 5, 2,00,000/- column 4...), so the columns do not line up and a figure read out of the index may belong to a different treatment. Read the grid on the PDF page directly

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B38.3 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1    60,000.00` |
| Key says payable | Rs 60,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p9 (index records p9) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i.
```

Arithmetic, as the key records it:

```
room rent within the eligible limit, so no proportionate deduction -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B38.4 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    22,000.00` |
| Key says payable | Rs 22,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B38.5 — Investigations - Pre-procedure Panel

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - Pre-procedure Panel            1     8,500.00` |
| Key says payable | Rs 8,500 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B39

| | |
|---|---|
| Policy | niva_bupa |
| Sum insured | Rs 1,000,000 |
| Policy start date | 2022-10-31 |
| Admission date | 2026-03-26 |
| Policy schedule | none supplied |
| Category | non_payable |
| Total charged | Rs 173,100 |
| Key total payable | Rs 47,000 |

### B39.1 — Room Rent (Single Private) 6,500 x 5 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Single Private) 6,500 x 5 days       5    32,500.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: pro-rata applies to a room "higher than the eligible room category as specified in your Policy Schedule" - no schedule supplied and no default stated - no rupee limit can be derived for this bill
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.2 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1    86,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
an associated medical expense, but 6.2.4 p26: pro-rata applies to a room "higher than the eligible room category as specified in your policy schedule" - no schedule supplied and no default stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.3 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    33,000.00` |
| Key says payable | Rs 33,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.4 — Gloves

| Field | Value |
|---|---|
| Bill line, as printed | `Gloves                                         28     1,700.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 1,700 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in niva_bupa.pdf p29 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 56: Gloves
```

Arithmetic, as the key records it:

```
IRDAI-List-I #56 "gloves" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.5 — Attendant Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Attendant Charges                               5     3,500.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 3,500 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in niva_bupa.pdf p29 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 24: Attendant Charges
```

Arithmetic, as the key records it:

```
IRDAI-List-I #24 "attendant charges" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.6 — Diaper of Any Type

| Field | Value |
|---|---|
| Bill line, as printed | `Diaper of Any Type                              1     1,400.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 1,400 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in niva_bupa.pdf p29 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 17: Diaper of Any Type
```

Arithmetic, as the key records it:

```
IRDAI-List-I #17 "diaper of any type" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.7 — Creams Powders Lotions (toiletries are not payable, only prescribed medical pharmaceuticals payable)

| Field | Value |
|---|---|
| Bill line, as printed | `Creams Powders Lotions (toiletries are not p    1       800.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 800 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in niva_bupa.pdf p29 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 54: Creams Powders Lotions (toiletries are not payable, only prescribed medical pharmaceuticals payable)
```

Arithmetic, as the key records it:

```
IRDAI-List-I #54 "creams powders lotions" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.8 — Birth Certificate

| Field | Value |
|---|---|
| Bill line, as printed | `Birth Certificate                               1       200.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 200 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in niva_bupa.pdf p29 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 26: Birth Certificate
```

Arithmetic, as the key records it:

```
IRDAI-List-I #26 "birth certificate" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B39.9 — Investigations - Labs and CT

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - Labs and CT                    1    14,000.00` |
| Key says payable | Rs 14,000 |
| Deduction | Rs 0 |
| clause_id | `6.2.4` |
| Located in the PDF on | p26 (index records p25) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
```

Arithmetic, as the key records it:

```
6.2.4 p26: "Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `6.2.4`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B41

| | |
|---|---|
| Policy | star_health |
| Sum insured | Rs 1,000,000 |
| Policy start date | 2021-03-18 |
| Admission date | 2026-05-04 |
| Policy schedule | none supplied |
| Category | room_category_limit |
| Total charged | Rs 327,500 |
| Key total payable | Rs 93,000 |

### B41.1 — Room Rent (Deluxe) 11,000 x 5 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Deluxe) 11,000 x 5 days              5    55,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
II.1 p10 table: Sum Insured 1,000,000 -> "Single Standard A/C Room" - a room category, no rupee limit stated - no rupee limit can be derived for this bill
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B41.2 — ICU Charges 16,000 x 2 days

| Field | Value |
|---|---|
| Bill line, as printed | `ICU Charges 16,000 x 2 days                     2    32,000.00` |
| Key says payable | Rs 32,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; ICU is outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 3: ICU is never proportionately reduced (all three policies place it outside AME)**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B41.3 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1   120,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
an associated medical expense, but ii.1 p10 table: sum insured 1,000,000 -> "single standard a/c room" - a room category, no rupee limit stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B41.4 — Anaesthetist Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Anaesthetist Charges                            1    26,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
an associated medical expense, but ii.1 p10 table: sum insured 1,000,000 -> "single standard a/c room" - a room category, no rupee limit stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B41.5 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    44,000.00` |
| Key says payable | Rs 44,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B41.6 — Operation Theatre Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Operation Theatre Charges                       1    32,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
an associated medical expense, but ii.1 p10 table: sum insured 1,000,000 -> "single standard a/c room" - a room category, no rupee limit stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B41.7 — Investigations - CT and Labs

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - CT and Labs                    1    17,000.00` |
| Key says payable | Rs 17,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B41.8 — Gloves

| Field | Value |
|---|---|
| Bill line, as printed | `Gloves                                         25     1,500.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 1,500 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 56: Gloves
```

Arithmetic, as the key records it:

```
IRDAI-List-I #56 "gloves" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B42

| | |
|---|---|
| Policy | star_health |
| Sum insured | Rs 1,000,000 |
| Policy start date | 2020-08-02 |
| Admission date | 2026-05-12 |
| Policy schedule | none supplied |
| Category | room_category_limit |
| Total charged | Rs 222,500 |
| Key total payable | Rs 45,500 |

### B42.1 — Room Rent (Deluxe) 9,800 x 4 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Deluxe) 9,800 x 4 days               4    39,200.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
II.1 p10 table: Sum Insured 1,000,000 -> "Single Standard A/C Room" - a room category, no rupee limit stated - no rupee limit can be derived for this bill
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B42.2 — Surgeon Fee

| Field | Value |
|---|---|
| Bill line, as printed | `Surgeon Fee                                     1    88,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
an associated medical expense, but ii.1 p10 table: sum insured 1,000,000 -> "single standard a/c room" - a room category, no rupee limit stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B42.3 — Anaesthetist Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Anaesthetist Charges                            1    19,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
an associated medical expense, but ii.1 p10 table: sum insured 1,000,000 -> "single standard a/c room" - a room category, no rupee limit stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B42.4 — Operation Theatre Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Operation Theatre Charges                       1    26,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
an associated medical expense, but ii.1 p10 table: sum insured 1,000,000 -> "single standard a/c room" - a room category, no rupee limit stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B42.5 — Medicines and Drugs

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines and Drugs                             1    31,000.00` |
| Key says payable | Rs 31,000 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B42.6 — Investigations - MRI and Labs

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - MRI and Labs                   1    14,500.00` |
| Key says payable | Rs 14,500 |
| Deduction | Rs 0 |
| clause_id | `II.1` |
| Located in the PDF on | p8 (index records p9) |
| Why this text | the sentence the key's derivation quotes, from I.Def45 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated medical expenses: Associated
Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of the Hospital where the Insured Person has been admitted and treated and hence Proportionate deduction will be applicable on these items.
```

Arithmetic, as the key records it:

```
I.Def45 p8: "Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/anaesthetist/Physician/Specialist ... does not include cost of pharmacy and consumables, cost of implants and medical devices and cost of diagnostics, ICU charges"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `II.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause II.1 does not contain - it is in ['I.Def45']

> **CANNOT SUPPORT:** clause_id is II.1 but the derivation reasons from I.Def45; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B42.7 — Consultant Visit Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Consultant Visit Charges                        4     4,800.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `II.1` |
| Located in the PDF on | p10 (index records p9) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less.
```

Arithmetic, as the key records it:

```
an associated medical expense, but ii.1 p10 table: sum insured 1,000,000 -> "single standard a/c room" - a room category, no rupee limit stated - whether a proportionate deduction applies cannot be determined
```

> **ASSUMPTION (differential billing): proportionate deduction applies - the policies disapply it at hospitals that do not follow differential billing, and nothing on a bill says whether this one does**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

| CONFIRMED | NOTES |
|---|---|
|  |  |

## B43

| | |
|---|---|
| Policy | hdfc_ergo |
| Sum insured | Rs 500,000 |
| Policy start date | 2021-10-09 |
| Admission date | 2026-05-18 |
| Policy schedule | none supplied |
| Category | schedule_missing |
| Total charged | Rs 264,000 |
| Key total payable | Rs 40,300 |

### B43.1 — Room Rent (Shared) 3,200 x 5 days

| Field | Value |
|---|---|
| Bill line, as printed | `Room Rent (Shared) 3,200 x 5 days               5    16,000.00` |
| Key says payable | Rs 16,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the sentence the key's derivation quotes |

Clause text, verbatim from `data/clauses.json`:

```
Room rent limit shall be ‘At Actuals’ unless otherwise specified in the Policy Schedule.
```

Arithmetic, as the key records it:

```
B.1.1 p11: "Room rent limit shall be 'At Actuals' unless otherwise specified in the Policy Schedule"; no schedule supplied, so At Actuals applies; charge is within entitlement -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B43.2 — AYUSH Inpatient Treatment Package

| Field | Value |
|---|---|
| Bill line, as printed | `AYUSH Inpatient Treatment Package               1    88,000.00` |
| Key says payable | **flagged `needs_human`** |
| Deduction | - |
| clause_id | `None` |
| Located in the PDF on | p12 |
| Why this text | the sentence the key's derivation quotes, from B.1.4 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
AYUSH Treatment
The Company shall indemnify the Medical Expenses incurred by the Insured Person only for Inpatient Care under Ayurveda, Yoga and Naturopathy, Unani, Siddha and Homeopathy systems of medicines during each Policy Year up to the Sub-limit specified against this Cover in the Policy Schedule, in any AYUSH Hospital.
```

Arithmetic, as the key records it:

```
B.1.4 p12: AYUSH is payable "up to the Sub-limit specified against this Cover in the Policy Schedule" - the wording states no figure and no schedule was supplied
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B43.3 — Consultant Visit Charges

| Field | Value |
|---|---|
| Bill line, as printed | `Consultant Visit Charges                        3     6,000.00` |
| Key says payable | Rs 6,000 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p11 (index records p11) |
| Why this text | the clause's first full sentence (its derivation quotes nothing) |

Clause text, verbatim from `data/clauses.json`:

```
Hospitalization Expenses
The Company shall indemnify Medical Expenses necessarily incurred by the Insured Person for Hospitalization of the Insured Person during the Policy Year due to Illness or Injury, up to the Sum Insured specified in the Policy Schedule for:
a.
```

Arithmetic, as the key records it:

```
room rent within the eligible limit, so no proportionate deduction -> paid in full
```

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B43.4 — Medicines - Ayurvedic Preparations

| Field | Value |
|---|---|
| Bill line, as printed | `Medicines - Ayurvedic Preparations              1    14,500.00` |
| Key says payable | Rs 14,500 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B43.5 — Investigations - Basic Panel

| Field | Value |
|---|---|
| Bill line, as printed | `Investigations - Basic Panel                    1     3,800.00` |
| Key says payable | Rs 3,800 |
| Deduction | Rs 0 |
| clause_id | `B.1.1` |
| Located in the PDF on | p8 (index records p11) |
| Why this text | the sentence the key's derivation quotes, from A.1.2.Def5 — the clause the derivation reasons from |

Clause text, verbatim from `data/clauses.json`:

```
Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category occupied by the insured person whilst undergoing treatment in some of the hospitals.
```

Arithmetic, as the key records it:

```
A.1.2.Def5 p8: "Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen ... do not include Cost of pharmacy and consumables, Cost of implants and medical devices and Cost of diagnostics. Proportionate deduction shall not be applicable to 'ICU charges'"; pharmacy, consumables, implants and diagnostics are outside associated medical expenses, so no proportionate deduction -> paid in full
```

> **ASSUMPTION 4: medicines, diagnostics and implants are never proportionately reduced**
>
> This row cannot be settled from the PDF alone.

> **ASSUMPTION (absent policy schedule): the clause defers the limit to a schedule that this bill does not supply**
>
> This row cannot be settled from the PDF alone.

> **Coverage check.** Paid in full. The only clause cited is `B.1.1`. Confirm it establishes that this item is **covered**, and not merely that no limit reduces it - "no deduction" is a claim that needs a citation of its own.

> **CANNOT SUPPORT:** the derivation quotes text that clause B.1.1 does not contain - it is in ['A.1.2.Def5']

> **CANNOT SUPPORT:** clause_id is B.1.1 but the derivation reasons from A.1.2.Def5; citation accuracy is scored on clause_id

| CONFIRMED | NOTES |
|---|---|
|  |  |

### B43.6 — Gloves

| Field | Value |
|---|---|
| Bill line, as printed | `Gloves                                         15       900.00` |
| Key says payable | Rs 0 |
| Deduction | Rs 900 |
| clause_id | `IRDAI-List-I` |
| Located in the PDF on | p1 |
| Why this text | data/non_payable.json, the IRDAI non-payable list - non_payable_items.pdf p1, and reproduced in hdfc_ergo.pdf p49 |

Clause text, verbatim from `data/non_payable.json`:

```
IRDAI List I, item 56: Gloves
```

Arithmetic, as the key records it:

```
IRDAI-List-I #56 "gloves" is a non-payable item -> nil
```

| CONFIRMED | NOTES |
|---|---|
|  |  |

## Appendix — the clauses in full

Every distinct clause cited above, quoted whole from `data/clauses.json`, so a
row's short quote can be read in its context.

### 6.2.4 — niva_bupa

*Claims* · index records page 25

```
Claims
a. Cashless claim facility is available at our network hospitals ONLY. As list of network hospitals is dynamic, for the latest list, refer to our website www.nivabupa.com.
b. Documents required with claim form:
Hospital / Medical records:
• Original Discharge summary with first and subsequent consultation papers.
• Original Final Hospital bill with detailed break-up and payment receipt (including pharmacy bills).
• Laboratory investigation reports with supporting prescriptions.
• MLC/First Information Report (FIR) (in accident cases).
Policyholder documents (Nominee in case of death of Policyholder):
• KYC documents • Cancelled cheque IMPORTANT:
• All documents MUST be submitted at the earliest possible time. .
• For any delay in submission, You MUST provide the reasons in writing.
We will condone such delay on merits (i.e. reasons beyond your control).
• You MUST submit all claim related documents for expenses within the Deductible amount (if applicable).
• We reserve the right to check and investigate the hospital / medical records from any doctor, Hospital, clinic, individual or institution.
c. The expenses that are not covered or subsumed into room charges / procedure charges / costs of treatment are placed as Annexure I.
d. If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula:
(Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners’ fees and operation theatre charges.
e. For any hospitalization, we will pay for items included in the bill by the Hospital during the duration of hospitalization. Items not included in the bill will not be paid.
Please Note:
i. Once the final authorization request is received for discharge, the same will be processed within three hours from the final documents received.
In case of delay from our end, any additional amount charged by the hospital will be borne by us. This amount will be paid over and above the policy limits.
ii. We offer Cashless Everywhere, even in hospitals which are not part of our network. For More details and process please visit our website:
https://transactions.nivabupa.com/cashlessclaims/pages/intimationclaim.aspx iii.Cashless Claim SettlementThe Company reserves the right to call for additional documents wherever required.
Grant of initial pre-authorization by the Company will be based on the information and documents made available at the time of processing of the request and shall be provisional in nature. The Company reserves the right to review, modify, withdraw or deny such authorization, in whole or in part, at any stage of hospitalization or treatment if subsequent information, medical records, diagnostic findings, discharge documents, investigation reports, or any other material evidence received by the Company indicates that the claim, in whole or in part, is not payable under the terms & conditions of the Policy. Grant of initial authorization shall not constitute as admission of liability, waiver of any policy term, nor shall it preclude the Company from undertaking further review of the claim in accordance with the Policy.
Denial of a pre-authorization request is no way to be construed as denial of treatment or denial of coverage. The Insured Person can go ahead with treatment, settle the hospital bills and submit the claim for a reimbursement of expenses.
```

### B.1.1 — hdfc_ergo

*Hospitalization Expenses* · index records page 11

```
Hospitalization Expenses
The Company shall indemnify Medical Expenses necessarily incurred by the Insured Person for Hospitalization of the Insured Person during the Policy Year due to Illness or Injury, up to the Sum Insured specified in the Policy Schedule for:
a. Room Rent, boarding, nursing expenses as provided by the Hospital / Nursing Home. Room rent limit shall be ‘At Actuals’ unless otherwise specified in the Policy Schedule.
b. Intensive Care Unit (ICU) / Intensive Cardiac Care Unit (ICCU) expenses. ICU limit (including ICCU) for bed charges shall be ‘At Actuals’ unless otherwise specified in the Policy Schedule.
c. Surgeon, anaesthetist, Medical Practitioner, consultants, specialist Fees during Hospitalization forming part of Hospital bill.
d. Investigative treatments and diagnostic procedures directly related to Hospitalization.
e. Medicines and drugs prescribed in writing by Medical Practitioner.
f. Intravenous fluids, blood transfusion, surgical appliances, allowable consumables and/or enteral feedings. Operation theatre charges.
g. The cost of prosthetics and other devices or equipment, if implanted internally during Surgery.
```

### B.1.1.1 — hdfc_ergo

*Other Expenses* · index records page 11

```
Other Expenses
i. Expenses incurred on road Ambulance if the Insured Person is required to be transferred to the nearest Hospital for Emergency Care or from one Hospital to another Hospital or from Hospital to Home (within same city) following Hospitalization.
ii. In patient Care Dental Treatment, necessitated due to disease or Injury
iii. Plastic Surgery, necessitated due to Injury
iv. All Day Care Treatments.
Note
i. Expenses of Hospitalization for a minimum period of 24 consecutive hours only shall be admissible. However, the time limit shall not apply in respect of Day Care Treatment.
ii. The Hospitalization must be for Medically Necessary Treatment, and prescribed in writing by Medical Practitioner.
iii. Proportionate deduction on Room Rent: In case the Insured Person is admitted in a room that exceeds the category/limit stipulated in the Policy Schedule, the reimbursement/payment of Room Rent charges including all Associated Medical Expenses incurred at Hospital shall be effected in the same proportion as the admissible rate per day bears to the actual rate per day of Room Rent charges. This condition is not applicable in respect of Hospitals where differential billing for Associated Medical Expenses is not followed based on Room Rent. In case the Insured Person is admitted in an ICU / ICCU room that exceeds the category/limit stipulated in the Policy Schedule then Proportionate deduction as stated above shall only apply on ICU / ICCU room charges for the days Insured Person was admitted in ICU / ICCU. Proportionate deduction will not apply for Associated Medical expenses incurred during the days Insured Person was admitted in ICU / ICCU.
```

### II.1 — star_health

*In-patient Treatment* · index records page 9

```
In-patient Treatment: We will cover the
following Medical Expenses incurred in respect of Hospitalization of the Insured Person during the Policy Period, up to the Sum Insured specified in the Policy Schedule against this In-Patient treatment:
i. Room, Boarding, Nursing Expenses all-inclusive as provided by the Hospital / Nursing Home as per the limits given below;
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 10,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 15,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 20,00,000/- - Limit (Rs.) Single Standard A/C Room
[table] Sum Insured (Rs.) 25,00,000/- - Limit (Rs.) Single Standard A/C Room
Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less. Proportionate deductions are not applied in respect of the hospitals which do not follow differential billing or for those expenses in respect of which differential billing is not adopted based on the room category.
ii. Surgeon, Anaesthetist, Medical Practitioner, Consultants, Specialist Fees.
iii. Anaesthesia, Blood, Oxygen, Operation theatre charges, ICU charges, Surgical appliances, Medicines and Drugs, Diagnostic materials and X-ray, Diagnostic imaging modalities, dialysis, chemotherapy, radiotherapy, cost of pacemaker, stent and similar expenses.
With regard to coronary stenting, medicines, Implants and such other similar items the Company will pay cost of stent as per the Drug Price Control Order (DPCO) / National Pharmaceuticals Pricing Authority (NPPA) Capping.
```

### II.5 — star_health

*Coverage for Modern Treatments* · index records page 11

```
Coverage for Modern Treatments: The follo
Period for the treatment/procedure (either the amount mentioned in table below. This Uterine Sum artery Balloon Deep Bra Insured Embolization Sinuplasty Stimulati (Rs.) and HIFU Limit per Policy Period for each treatm 1,00,000/- 12,500/- 5,000/- 25,000/2,00,000/- 25,000/- 10,000/- 50,000/3,00,000/- 37,500/- 15,000/- 75,000/4,00,000/- 1,00,000/- 40,000/- 2,00,000/ 5,00,000/- 1,25,000/- 50,000/- 2,50,000/ 10,00,000/- 1,50,000/- 1,00,000/- 3,00,000/ 15,00,000/- 1,75,000/- 1,25,000/- 4,00,000/ 20,00,000/- 2,00,000/- 1,50,000/- 4,50,000/ 25,00,000/- 2,00,000/- 1,50,000/- 5,00,000/ * Sublimits are all inclusive with or without hospita post hospitalization.
Sum Stereotactic Robotic Bronchic Insured radio surgeries Thermop (Rs.) surgeries Limit per Policy Perio 1,00,000/- 25,000/- 25,000/2,00,000/- 50,000/- 50,000/3,00,000/- 75,000/- 75,000/4,00,000/- 2,00,000/- 1,75,000/5,00,000/- 2,50,000/- 2,00,000/10,00,000/- 3,00,000/- 2,25,000/15,00,000/- 4,00,000/- 2,50,000/20,00,000/- 4,50,000/- 2,75,000/25,00,000/- 5,00,000/- 3,00,000/owing expenses are payable during the Policy
[table] Sum Insured (Rs.) - Uterine artery Embolization and HIFU - Balloon Sinuplasty - Deep Brain Stimulation - Oral Chemotherapy* (Sublimits including Pre and Post Hospitalization) - Immunotheraphy- Monoclonal Antibody to be given as injection - Intra Vitreal injections
[table] Sum Insured (Rs.) - Limit per Policy Period for each treatment/procedure (Rs.) - Balloon Sinuplasty - Deep Brain Stimulation - Oral Chemotherapy* (Sublimits including Pre and Post Hospitalization) - Immunotheraphy- Monoclonal Antibody to be given as injection - Intra Vitreal injections
[table] 1,00,000/- - 12,500/- - 5,000/- - 25,000/- - 12,500/- - 25,000/- - 5,000/-
[table] 2,00,000/- - 25,000/- - 10,000/- - 50,000/- - 25,000/- - 50,000/- - 10,000/-
[table] 3,00,000/- - 37,500/- - 15,000/- - 75,000/- - 37,500/- - 75,000/- - 15,000/-
[table] 4,00,000/- - 1,00,000/- - 40,000/- - 2,00,000/- - 1,00,000/- - 2,00,000/- - 40,000/-
[table] 5,00,000/- - 1,25,000/- - 50,000/- - 2,50,000/- - 1,25,000/- - 2,50,000/- - 50,000/-
[table] 10,00,000/- - 1,50,000/- - 1,00,000/- - 3,00,000/- - 2,00,000/- - 4,00,000/- - 75,000/-
[table] 15,00,000/- - 1,75,000/- - 1,25,000/- - 4,00,000/- - 2,50,000/- - 5,00,000/- - 1,00,000/-
[table] 20,00,000/- - 2,00,000/- - 1,50,000/- - 4,50,000/- - 2,75,000/- - 5,50,000/- - 1,25,000/-
[table] 25,00,000/- - 2,00,000/- - 1,50,000/- - 5,00,000/- - 3,00,000/- - 6,00,000/- - 1,50,000/-
[table] * Sublimits are all inclusive with or without hospitalization wherever hospitalization includes pre and post hospitalization. - 2,00,000/- - 1,50,000/- - 5,00,000/- - 3,00,000/- - 6,00,000/- - 1,50,000/-
[table] 25,00,000/- - 2,00,000/- - 1,50,000/- - 5,00,000/- 3,00,000/- 6,00,000/- - 00,000/- 6,0 - 00,000/- - 1,50,000/-
[table] Sum Insured (Rs.) - Robotic surgeries - Stereotactic radio surgeries - Bronchical Thermoplasty - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - Stem cell therapy: Hematopoietic stem cells for bone marrow transplant for haematological conditions
[table] Sum Insured (Rs.) - Limit per Policy Period for each treatment/procedure (Rs.) - Stereotactic radio surgeries - Bronchical Thermoplasty - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - Stem cell therapy: Hematopoietic stem cells for bone marrow transplant for haematological conditions
[table] 1,00,000/- - 25,000/- - 25,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 25,000/-
[table] 2,00,000/- - 50,000/- - 50,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 50,000/-
[table] 3,00,000/- - 75,000/- - 75,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 75,000/-
[table] 4,00,000/- - 2,00,000/- - 1,75,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 2,00,000/-
[table] 5,00,000/- - 2,50,000/- - 2,00,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 2,50,000/-
[table] 10,00,000/- - 3,00,000/- - 2,25,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 3,00,000/-
[table] 15,00,000/- - 4,00,000/- - 2,50,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 4,00,000/-
[table] 20,00,000/- - 4,50,000/- - 2,75,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 4,50,000/-
[table] 25,00,000/- - 5,00,000/- - 3,00,000/- - Up to Sum Insured - Vaporisation of the prostate (Green laser treatment or holmium laser treatment) - IONM-(Intra Operative Neuro Monitoring) - 5,00,000/-
```

### II.8 — star_health

*Road ambulance* · index records page 12

```
Road ambulance: Subject to an admissible
hospitalization claim, road ambulance expenses up to Rs.750/- per hospitalization and up to Rs.1,500/- per Policy Period shall be payable for the following:
i. f or transportation of the Insured Person by private ambulance service to go to hospital when this is needed for medical reasons or
ii. for transportation of the Insured Person by private ambulance service from one hospital to another hospital for better medical treatment or
iii. for transportation of the Insured Person from the hospital where treatment is taken to their place of residence (if it is in same city) provided the requirement of an ambulance to the residence is certified by the medical practitioner
```

