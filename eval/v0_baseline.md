# v0 — naive baseline

The first working audit: one search per bill line, one judge call, Python does
the arithmetic. No retry when the model is unsure, no query rewriting, no
non-payable fast path, no second pass.

It is meant to be wrong. Building the agent first would leave no way to show it
helped, so this run is the number every later version is measured against.

## Run

```
uv run python -m core.audit data/sample_bill.txt --policy star_health --sum-insured 500000
```

`data/sample_bill.txt`, Star Health, sum insured Rs 5,00,000, 5-day stay.

## Output

| item | charged | v0 allowed | clause cited |
|---|---:|---:|---|
| room rent (single a/c) | 40,000.00 | 40,000.00 | II.1 |
| icu charges | 60,000.00 | FLAGGED | II.15 |
| surgeon fee | 80,000.00 | 50,000.00 | II.5 |
| anaesthetist charges | 15,000.00 | FLAGGED | II.15 |
| medicines and drugs | 38,000.00 | 38,000.00 | II.1 |
| surgical gloves | 1,200.00 | 1,200.00 | II.5 |
| disposable syringes | 800.00 | FLAGGED | II.15 |
| admission / registration charges | 1,500.00 | FLAGGED | II.15 |
| attendant charges | 2,500.00 | 2,500.00 | II.20 |
| ambulance charges | 1,000.00 | 1,000.00 | II.8 |
| **TOTAL** | **240,000.00** | **132,700.00** | 4 lines flagged |

The model is not fully deterministic, so exact figures drift between runs. The
failure *modes* below are stable.

## What it got wrong, and why

| Line | v0 gave | Should be | Cause |
|---|---|---|---|
| Room rent 8,000 x 5 | 40,000 | capped at the per-day limit | Retrieved the right clause (II.1) but did not extract the per-day figure from the table inside it |
| Surgical gloves | 1,200 | 0 | Gloves are on the IRDAI non-payable list. v0 has no fast path, so it searched the policy and found nothing that excludes them |
| Surgeon fee | 50,000 | 80,000 | Cited II.5 (Modern Treatments), which does not govern surgeon fees. A wrong clause producing a confident number is worse than an abstention |
| ICU, syringes, admission | flagged | should resolve | One search, one attempt. The first query missed, and there is no rewriting |
| Every other line | unchanged | scaled to the room-rent ratio | Room rent breached its limit, so the associated expenses should all be reduced proportionately |

## The failure no per-line system can fix

Nothing in the surgeon's fee line mentions room rent. Judged on its own it looks
entirely correct. But once room rent exceeds the eligible limit, Star Health's
clause II.1 reduces *every* associated medical expense in the same proportion —
so one breached limit silently rewrites the rest of the bill.

No amount of better retrieval or a smarter judge finds this, because the
information needed is not in the line being judged. It needs a pass that runs
after every line has a verdict, which is why the second pass exists and why it
is the most important part of the project.

## Baseline metrics

To be filled by `eval/evaluate.py` once the answer key is complete. This file
records the qualitative failure modes; `eval/results.md` will carry the v0-v4
numbers.

| Metric | v0 |
|---|---|
| Line accuracy | |
| Clause accuracy | |
| Payout error | |
| Abstention correctness | |
| False answers | |
| Fabricated clauses | |
| p95 latency | |
| Avg tool calls | 1 search + 1 judge per line, fixed |


---

## Note on the evaluation set (added after v0 was recorded)

The first 40 bills tagged 10 as `room_rent_over`. Nine were impossible:

- **Star Health** caps by rupee only at 3L and 4L sum insured. From 5L up the wording gives a room *category* ("Single Standard A/C Room"), so B01, B19 and B33 could never breach a rupee limit. Their sum insured was corrected to 3L/4L.
- **HDFC Ergo** states room rent as "At Actuals unless otherwise specified in the Policy Schedule" — no figure exists in the document.
- **Niva Bupa** caps by room category per the Policy Schedule, again with no figure in the wording.

The six HDFC and Niva bills now carry an optional `policy_schedule`, and four
bills were added: B41/B42 (Star Health at 10L, room category, no rupee limit
derivable) and B43/B44 (HDFC and Niva with no schedule at all). Those four must
return `needs_human`.

The error was mine: categories were assigned from bill content without checking
that each policy could produce that rule. It is worth recording because the
flattened room rent table would have produced exactly the same mistake at
runtime - reading `5,00,000` as capped at Rs 5,000/day.
