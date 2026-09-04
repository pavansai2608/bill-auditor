# Retrieval recall - before the phantom-space fix - 2026-09-04

44 bills. Clause index `f253c5afef81`.

**recall@3 is the ceiling on citation accuracy.** The judge is shown three
clauses; a line whose answer is not among them cannot be got right, however
the model is prompted.

| scope | lines | recall@3 | recall@3 over 3 angles | recall@20 | in the candidate set |
|---|---|---|---|---|---|
| **all** | 261 | 36.8% | 52.1% | 72.0% | 72.0% |
| hdfc_ergo | 81 | 43.2% | 63.0% | 55.6% | 55.6% |
| niva_bupa | 74 | 40.5% | 56.8% | 94.6% | 94.6% |
| star_health | 106 | 29.2% | 40.6% | 68.9% | 68.9% |

| category | lines | recall@3 | recall@3 over 3 angles | recall@20 | in the candidate set |
|---|---|---|---|---|---|
| clean | 65 | 41.5% | 49.2% | 78.5% | 78.5% |
| non_payable | 41 | 36.6% | 43.9% | 61.0% | 61.0% |
| room_category_limit | 14 | 28.6% | 35.7% | 71.4% | 71.4% |
| room_rent_over | 75 | 37.3% | 72.0% | 72.0% | 72.0% |
| schedule_missing | 10 | 40.0% | 70.0% | 80.0% | 80.0% |
| sub_limit | 25 | 32.0% | 40.0% | 64.0% | 64.0% |
| waiting_period | 31 | 32.3% | 32.3% | 77.4% | 77.4% |

**Lines retrieval never sees**

- 61 — settled on the non-payable list, no search runs
- 6 — the key flags this line, so nothing is retrievable

## Missed by every angle — 125 lines

Where the cited clause ended up. `not retrieved at all` means it was not in
the reranked list at any depth, which is a candidate-set problem rather than a
ranking one.

| bill | line | key cites | rule type | where it ranked | what ranked first |
|---|---|---|---|---|---|
| B01 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B01 | Investigations - CT and Bloodwork | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B01 | Disposable Syringes | `II.1` | other | not retrieved at all | `II.13` |
| B02 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B03 | Cataract Surgery - Right Eye Package | `6.2.4` | waiting_period | not retrieved at all | `5.1.2` |
| B03 | Intraocular Lens | `6.2.4` | other | ranked 17 | `5.1.2` |
| B03 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B03 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B03 | Pre-operative Investigations | `6.2.4` | other | ranked 12 | `5.1.2` |
| B04 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B05 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B05 | Anaesthetist Charges | `II.1` | other | ranked 7 | `II.25` |
| B05 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B05 | Investigations - Ultrasound and Labs | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B05 | Consultant Visit Charges | `II.1` | other | ranked 11 | `II.16` |
| B06 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B06 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B07 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B07 | Investigations - Endoscopy | `I.Def45` | other | not retrieved at all | `IV.14` |
| B07 | Consultant Visit Charges | `I.Def45` | other | not retrieved at all | `II.16` |
| B08 | Room Rent (Shared) 3,500 x 2 days | `C.1` | room_rent | not retrieved at all | `B.1.1.1` |
| B08 | Anaesthetist Charges | `C.1` | other | not retrieved at all | `B.1.1` |
| B08 | Operation Theatre Charges | `C.1` | other | not retrieved at all | `B.1.1` |
| B08 | Medicines and Drugs | `C.1` | other | ranked 8 | `B.1.1` |
| B09 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B09 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B09 | Investigations - Labs | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B10 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B10 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B10 | Consultant Visit Charges | `6.2.4` | other | ranked 18 | `5.1.2` |
| B11 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B11 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B12 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B12 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B12 | Investigations - Pre-op Panel | `I.Def45` | other | not retrieved at all | `IV.14` |
| B13 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B13 | Investigations - Labs | `A.1.2.Def5` | other | not retrieved at all | `C.2` |
| B14 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B14 | Anaesthetist Charges | `II.1` | other | ranked 7 | `II.25` |
| B14 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B14 | Investigations - Labs and Imaging | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B15 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B15 | Investigations - CT, Labs | `A.1.2.Def5` | other | not retrieved at all | `E.1.4` |
| B16 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B16 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B16 | Consultant Visit Charges | `6.2.4` | other | ranked 18 | `5.1.2` |
| B17 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B17 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B17 | Investigations - Labs | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B18 | Room Rent (Shared) 3,000 x 2 days | `5.1.2` | room_rent | ranked 14 | `6.2.4` |
| B19 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B19 | Investigations - PET CT | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B20 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B20 | Investigations - Labs and CT | `A.1.2.Def5` | other | not retrieved at all | `E.1.4` |
| B21 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B21 | Ambulance | `B.1.1` | sub_limit | not retrieved at all | `A.1.2.Def27` |
| B21 | Investigations - Labs | `A.1.2.Def5` | other | not retrieved at all | `C.2` |
| B22 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B22 | Anaesthetist Charges | `II.1` | other | ranked 7 | `II.25` |
| B22 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B22 | Investigations - Angiography | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B22 | Consultant Visit Charges | `II.1` | other | ranked 11 | `II.16` |
| B23 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B23 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B24 | Medicines - Ayurvedic Preparations | `A.1.2.Def5` | other | not retrieved at all | `B.1.4` |
| B25 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B25 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B25 | Consultant Visit Charges | `6.2.4` | other | ranked 18 | `5.1.2` |
| B26 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B26 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B26 | Investigations - MRI | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B27 | Room Rent (Shared) 3,500 x 3 days | `III.2` | room_rent | ranked 19 | `II.1` |
| B27 | Knee Implant | `III.2` | other | ranked 10 | `II.5` |
| B27 | Anaesthetist Charges | `III.2` | other | ranked 17 | `II.25` |
| B27 | Operation Theatre Charges | `III.2` | other | ranked 15 | `I.Def45` |
| B27 | Medicines and Drugs | `III.2` | other | ranked 13 | `II.16` |
| B27 | Physiotherapy Sessions | `III.2` | sub_limit | not retrieved at all | `II.5` |
| B28 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B28 | Investigations - PET CT and Labs | `A.1.2.Def5` | other | not retrieved at all | `E.1.4` |
| B29 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B29 | Investigations - Labs | `A.1.2.Def5` | other | not retrieved at all | `C.2` |
| B30 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B30 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B31 | Cataract Surgery - Right Eye | `6.2.4` | waiting_period | not retrieved at all | `5.1.2` |
| B31 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B31 | Pre-operative Investigations | `6.2.4` | other | ranked 12 | `5.1.2` |
| B32 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B32 | Anaesthetist Charges | `II.1` | other | ranked 7 | `II.25` |
| B32 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B32 | Investigations - Labs and USG | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B33 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B33 | Investigations - CT, MRI, Labs | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B34 | Room Rent (Single A/C) 5,500 x 2 days | `C.1` | room_rent | not retrieved at all | `B.1.1.1` |
| B34 | Anaesthetist Charges | `C.1` | other | not retrieved at all | `B.1.1` |
| B34 | Operation Theatre Charges | `C.1` | other | not retrieved at all | `B.1.1` |
| B34 | Medicines and Drugs | `C.1` | other | ranked 8 | `B.1.1` |
| B34 | Investigations - USG and Labs | `C.1` | other | ranked 13 | `E.1.4` |
| B35 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B35 | Investigations - Labs | `A.1.2.Def5` | other | not retrieved at all | `C.2` |
| B36 | Medicines and Drugs | `A.1.2.Def5` | other | not retrieved at all | `B.1.1` |
| B36 | Investigations - Labs | `A.1.2.Def5` | other | not retrieved at all | `C.2` |
| B37 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B37 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B38 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B38 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B38 | Investigations - Pre-procedure Panel | `I.Def45` | other | not retrieved at all | `IV.14` |
| B39 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B39 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
| B40 | Room Rent (Shared) 2,800 x 2 days | `III.2` | room_rent | ranked 19 | `II.1` |
| B40 | Anaesthetist Charges | `III.2` | other | ranked 17 | `II.25` |
| B40 | Operation Theatre Charges | `III.2` | other | ranked 15 | `I.Def45` |
| B40 | Medicines and Drugs | `III.2` | other | ranked 13 | `II.16` |
| B40 | Investigations - Basic Panel | `III.2` | other | ranked 15 | `IV.14` |
| B41 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B41 | Anaesthetist Charges | `II.1` | other | ranked 7 | `II.25` |
| B41 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B41 | Investigations - CT and Labs | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B42 | Surgeon Fee | `II.1` | other | ranked 5 | `I.Def55` |
| B42 | Anaesthetist Charges | `II.1` | other | ranked 7 | `II.25` |
| B42 | Medicines and Drugs | `I.Def45` | other | not retrieved at all | `II.16` |
| B42 | Investigations - MRI and Labs | `I.Def45` | other | not retrieved at all | `I.Def55` |
| B42 | Consultant Visit Charges | `II.1` | other | ranked 11 | `II.16` |
| B43 | Medicines - Ayurvedic Preparations | `A.1.2.Def5` | other | not retrieved at all | `B.1.4` |
| B44 | Surgeon Fee | `6.2.4` | other | ranked 9 | `4.1.2` |
| B44 | Medicines and Drugs | `6.2.4` | other | ranked 14 | `5.1.2` |
