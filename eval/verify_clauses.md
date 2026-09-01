# Clause verification sheet

Every clause the 44 evaluation bills depend on, as the system reads it **today**
— regenerated against the final index (402 clauses) after the table fix, the
cross-reference pass and the extraction repairs.

Check the *extracted value* against the PDF page listed. The last column is the
specific fact to confirm; where it is bold, an answer key entry is wrong if that
fact is wrong. The *refs* column shows clauses now retrieved alongside this one.

Nothing here was produced by the auditor. Clause selection is keyword routing
over the bill line items; values are copied verbatim from `data/clauses.json`.

## star_health

| clause_id | page | refs | extracted value | what I must confirm |
|---|---|---|---|---|
| `I.Def41` | 7 | — | Room Rent: Room Rent means the amount charged by a Hospital towards Room and Boarding expenses and shall include the associated medical expenses. | Confirm Room Rent **includes** associated medical expenses — that phrase is what carries the proportionate deduction through to the surgeon's fee. |
| `I.Def45` | 8 | — | Associated medical expenses: Associated Medical Expenses means expenses that shall include the applicable nursing charges, Operation theatre charges, Professional fees of Medical Practitioner including Surgeon/ anaesthetist/ Physician/Specialist of t | Confirm exactly which charges are Associated Medical Expenses, and whether ICU sits inside or outside that set. |
| `II.1` | 9 | — | [table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day [table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day [table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day [table] Sum Insured (Rs.) 4,00, | **Confirm 3L and 4L map to Rs 5,000/day, and that 5L and above give a room CATEGORY with no rupee cap.** Every star_health room-rent bill turns on this. |
| `II.1` | 9 | — | Note: Expenses relating to Associated medical expenses will be considered in proportion to the eligible room rent/room category stated in the policy schedule or actuals whichever is less. Proportionate deductions are not applied in respect of the hos | Confirm the proportionate-deduction Note and its differential-billing carve-out. The audit **assumes** differential billing applies — see README, Known assumptions. |
| `II.20` | 18 | — | [table] Sum Insured (Rs.) - Limit per day (Rs.) [table] 1,00,000/- - Not Available [table] 2,00,000/- - Not Available [table] 3,00,000/- - 800/- per day [table] 4,00,000/- - 800/- per day [table] 5,00,000/- - 800/- per day [table] 10,00,000/- - 800/- | Confirm the shared-accommodation figure (800/1000 per day) is a benefit paid TO the insured, not a cap on room rent. Easy to confuse with II.1. |
| `II.5` | 11 | — | [table] Sum Insured (Rs.) - Uterine artery Embolization and HIFU - Balloon Sinuplasty - Deep Brain Stimulation - Oral Chemotherapy* (Sublimits including Pre and Post Hospitalization) - Immunotheraphy- Monoclonal Antibody to be given as injection - In | **Confirm which column is Robotic Surgery and which is Stem Cell.** Headers now read correctly, but B12 and B38 depend on picking the right one. |
| `II.8` | 12 | — | Road ambulance: Subject to an admissible hospitalization claim, road ambulance expenses up to Rs.750/- per hospitalization and up to Rs.1,500/- per Policy Period shall be payable for the following: i. f or transportation of the Insured Person by priv | Confirm **both** limits: Rs 750 per hospitalisation AND Rs 1,500 per policy period. `JudgeOutput.limits` can now carry both; check they are both stated. |
| `II.9` | 12 | — | Air Ambulance charges up to 10% of the Sum Insured during the entire Policy Period, provided that; i. It is for life threatening emergency health condition/s of the Insured Person which requires immediate and rapid ambulance transportation to the hos | Confirm air ambulance is 10% of sum insured and available only at 5L and above. |
| `II.11` | 13 | — | Organ Donor Expenses for organ transplantation where the Insured Person is the recipient are payable provided the claim for transplantation is payable and subject to the availability of the Sum Insured. Donor screening expenses and post-donation comp | Confirm this is **10% of sum insured OR Rs 1,00,000, whichever is less** — two limits, lowest wins. |
| `II.19` | 17 | `III.3`, `III.1`, `III.2` | Hospitalization expenses for treatment of New Born Baby: The coverage for New Born Baby starts from the 16th day after its birth till the expiry date of the policy and is subject to a limit of 10% of the Sum Insured or Rupees Fifty thousand, whicheve | Confirm the newborn limit (10% of SI or Rs 50,000, lower) and that it disapplies Excl 01/02/03. |
| `II.28` | 21 | `II.1`, `II.2`, `II.3`, `II.4`, `II.5`, `II.6`, `II.7`, `II.8`, `II.9`, `II.11`, `II.13` | Mandatory Co-payment (Applicable for Coverages II.1, II.2, II.3, II.4, II.5, II.6, II.7, II.8, II.9, II.11 and II.13): This policy is subject to co-payment of 20% of each and every claim amount for fresh as well as renewal policies for Insured Person | **Confirm exactly which coverages the 20% co-payment applies to**, and that it starts at entry age 61. The scoping list is now retrieved with the clause. |
| `III.2` | 28 | — | Specified disease / procedure waiting period - Code Excl 02 a. E xpenses related to the treatment of the following listed Conditions, surgeries/ treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of incep | Confirm the 24-month specified-disease list covers hernia, cataract, knee replacement, hysterectomy, piles/fistula. Note it says *the longer of two waiting periods applies* — a prose reference the retriever cannot follow. |
| `III.3` | 29 | — | 30-day waiting period - Code Excl 03 A. Expenses related to the treatment of any illness within 30 days from the first policy commencement date shall be excluded except claims arising due to an accident, provided the same are covered B. This exclusio | Confirm the 30-day initial waiting period and its accident exception. |
| `III.31` | 32 | — | Hospital registration charges, admission charges, record charges, telephone charges and such other charges - Code Excl 34 | Confirm registration and admission charges are excluded. |
| `III.4` | 30 | — | Investigation & Evaluation - Code Excl 04 A. Expenses related to any admission primarily for diagnostics and evaluation purposes only are excluded B. Any diagnostic expenses which are not related or not incidental to the current diagnosis and treatme | Confirm admissions purely for investigation are excluded, and that ordinary diagnostics during a valid admission are not. |

## hdfc_ergo

| clause_id | page | refs | extracted value | what I must confirm |
|---|---|---|---|---|
| `A.1.1.Def41` | 2 | — | Room Rent means the amount charged by a Hospital towards Room and Boarding expenses and shall include the associated medical expenses. | Confirm Room Rent includes associated medical expenses. |
| `A.1.2.Def5` | 8 | — | Associated Medical Expenses means Consultation fees, charges on Operation theatre, surgical appliances & nursing, and expenses on Anesthesia, blood, oxygen incurred during Hospitalization of the Insured Person which vary based on the room category oc | Confirm the exact list of Associated Medical Expenses — this set is what the pro-rata multiplies. |
| `B.1.1` | 11 | — | Room Rent, boarding, nursing expenses as provided by the Hospital / Nursing Home. Room rent limit shall be ‘At Actuals’ unless otherwise specified in the Policy Schedule. b. Intensive Care Unit (ICU) / Intensive Cardiac Care Unit | **Confirm room rent is 'At Actuals' unless the Policy Schedule says otherwise.** This is why the optional 4th input exists. Confirm ICU is on the same basis. |
| `B.1.1.1` | 11 | — | Proportionate deduction on Room Rent: In case the Insured Person is admitted in a room that exceeds the category/limit stipulated in the Policy Schedule, the reimbursement/payment of Room Rent charges including all Associated Medical Expenses incurre | Confirm the pro-rata formula and the differential-billing carve-out. Confirm whether ICU is treated the same way. |
| `B.1.4` | 12 | — | AYUSH Treatment The Company shall indemnify the Medical Expenses incurred by the Insured Person only for Inpatient Care under Ayurveda, Yoga and Naturopathy, Unani, Siddha and Homeopathy systems of medicines during each Policy Year up to the Sub-limi | Confirm the AYUSH limit for B24 — rupee cap, % of sum insured, or at actuals. |
| `C.1` | 28 | — | Waiting Periods All the Waiting Periods and exclusions listed below shall be applicable individually for each Insured Person and claims shall be assessed accordingly. a. Pre-Existing Diseases: Code – Excl01 i. Expenses related to the treatment of a p | Confirm the waiting-period table: 30 days, 24/36 months specified disease, PED. B08 and B34 depend on it. |
| `C.2` | 30 | — | Standard Exclusions a. Investigation & Evaluation: Code Excl04 i. Expenses related to any admission primarily for diagnostics and evaluation purposes only are excluded. ii. Any diagnostic expenses which are not related or not incidental to the curren | Confirm the standard exclusion codes, and whether consumables are excluded here as well as on the IRDAI list. |
| `C.3` | 32 | — | Specific Exclusions: In addition to the foregoing general exclusions, the Company shall not be liable to make any payment under this Policy caused by or arising out of or attributable to any of the following: a. War or any act of war, invasion, act o | Confirm the specific exclusions for anything B13/B21/B35 bills. |
| `A.1.1.Def8` | 2 | — | Co-Payment means a cost sharing requirement under a health insurance policy that provides that the policyholder/insured will bear a specified percentage of the admissible claims amount. A co-payment does not reduce the Sum Insured. | Confirm the co-payment definition and whether any co-pay applies by default on Optima Secure. |
| `B.2.13` | 25 | `B.1.1`, `B.1.1.1` | Modification of Room Rent On availing this option, Room Rent category shall stand modified and will be as stipulated in the Policy Schedule. Policyholders may re-configure their selection only at the time of renewals subject to Underwriting. All othe | Confirm 'Modification of Room Rent' is an OPTIONAL add-on — do not apply it unless the schedule says it was bought. |

## niva_bupa

| clause_id | page | refs | extracted value | what I must confirm |
|---|---|---|---|---|
| `2.1.40` | 5 | — | Room Rent means the amount charged by a Hospital towards Room and Boarding expenses and shall include the associated medical expenses. 2.1.41. Surgery or Surgical Procedure means manual and / or operative procedure (s) required for treatment of an Il | Confirm Room Rent includes associated medical expenses. |
| `6.2.4` | 25 | — | room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula: (Eligib | **Confirm the pro-rata formula and exactly which charges it names** (room rent, nursing, practitioners' fees, OT). It does NOT list medicines or investigations — check whether that is really so. |
| `4.21` | 14 | — | Room Type Modification You can as per your lifestyle, choose to change the room category we are offering, and opt for what suits you best! You may choose between a Single Private Room and a Sharing Room based on your needs. Irrespective of the Room t | Confirm room type is Single Private vs Sharing, that ICU is always paid to base sum insured, and that the eligible limit comes from the schedule. |
| `5.1.2` | 15 | — | Specified disease/procedure waiting period (Code- Excl02) a. Expenses related to the treatment of the listed conditions, surgeries/treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception of the fi | Confirm the 24-month list covers cataract, hernia, joint replacement, hysterectomy. B18 and B31 depend on it. |
| `5.1.3` | 15 | — | 30-day waiting period (Code- Excl03): a. Expenses related to the treatment of any Illness within 30 days from the first Policy commencement date shall be excluded except claims arising due to an Accident, provided the same are covered. b. This exclus | Confirm the 30-day initial waiting period. |
| `4.19` | 14 | — | Co-Payment: It is the percentage of admissible claim amount You would have to bear, Rest we will pay. Note: Co-payment will NOT apply to Annual Health Check-up, Live Healthy, Second Medical Opinion, Shared Accommodation Cash, e-consultation, Personal | Confirm whether co-payment is mandatory or optional on ReAssure 2.0, and at what age. |
| `4.18` | 14 | — | Annual Aggregate Deductible This is an aggregate amount in a year that is incurred by you on Expenses in reaching a Hospital, Expenses during Hospitalization, Expenses before and after hospitalization, Home Care / Domiciliary Treatment, Organ Donor, | Confirm the annual aggregate deductible is optional and not applied unless chosen. |
| `5.1.4` | 16 | — | Investigation & Evaluation (Code-Excl04) a. Expenses related to any admission primarily for diagnostics and evaluation purposes only are excluded. b. Any diagnostic expenses which are not related or not incidental to the current diagnosis and treatme | Confirm the investigation-and-evaluation exclusion. |

## IRDAI non-payable list

| source | count | what I must confirm |
|---|---|---|
| `data/non_payable.json`, cite as `IRDAI-List-I` | 68 items | Confirm **Gloves, Attendant Charges, Mask, Kidney Tray, ECG Electrodes, Nebulisation Kit, Oxygen Mask, Television Charges, Surcharges** are listed, and that **Disposable Syringes is NOT**. B01 and B09 bill syringes; whether they are payable is your call, and the key decides it. |

---

# Failure-class scan — status after the fixes

| # | class | status |
|---|---|---|
| 1 | ambiguous units | **fixed** — `JudgeOutput.limits` carries every limit with its own `basis` |
| 2 | percentage vs rupee cap | **fixed** — same list, `money` takes the minimum |
| 3 | differential billing | **decided** — assumed true, stated in every report, `--no-differential-billing` to disable |
| 4 | cross-references | **half fixed** — id references pulled in at retrieval; prose references still open |
| 5 | extraction defects | **fixed** — II.5 headers, HDFC plan grid, niva fragments |

## Still open, by design

**Prose cross-references.** `star_health III.2` says *"the longer of the two
waiting periods shall apply"*, naming the pre-existing-disease period in words
with no clause id to match. `find_refs` cannot see it. The judge would need to
say *"I need another clause, and here is which one"* — which is the motivation
for the Phase 6 agent loop, not something retrieval can solve.

`refs` coverage as it stands: 6 star_health clauses, 19 hdfc_ergo, 0 niva_bupa.
Niva Bupa's wording cites almost nothing by number, so its clauses are read in
isolation. Worth remembering when reading any Niva verdict.

**The differential-billing precondition** is an assumption, not a finding. If a
key entry assumes proportionate deduction fired, that matches the default; if
you decide a bill should not have it, the eval must pass
`differential_billing=False` or the comparison is unfair.

## Low-confidence extractions that remain

| what | count | note |
|---|---|---|
| clauses containing a rendered table | ~35 | `II.1`, `II.20`, `II.5` verified by eye; the rest are not |
| deep nested lists over 800 chars | ~70 | list nesting is flattened, so a sub-item can lose its parent's context |
| lakh-format figures with no adjacent unit | ~15 | mostly HDFC plan-comparison grids, where the unit lives in the column header |

`star_health II.5` deserves a second look even though the headers now read
correctly: it is a six-column grid, and picking the wrong column gives a wrong
answer carrying a valid citation. B12 (robotic surgery) and B38 (stem cell
therapy) are the two bills exposed to it.
