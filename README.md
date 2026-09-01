# Bill Auditor

Audits Indian health insurance claim bills against the policy that governs them,
and shows which clause caused each deduction.

> Results, architecture and the full write-up are built in Phase 11.
> This file currently records only decisions that change how the system is used.

## Inputs

| Input | Required | Notes |
|---|---|---|
| The bill | yes | upload or paste |
| Insurer | yes | dropdown |
| Sum insured | yes | dropdown |
| Policy start date | yes | dropdown |
| **Room limit as per your policy schedule** | **no** | blank by default |

### Why there is a fourth, optional input

Two of the three policies do not state a room rent figure anywhere in their
wording:

- **HDFC Ergo** — "Room rent limit shall be *'At Actuals'* unless otherwise specified in the Policy Schedule" (clause B.1.1)
- **Niva Bupa** — caps by room *category* "as specified in your Policy Schedule" (clause 6.2.4)

Only **Star Health** carries a table keyed on sum insured, and even that gives a
rupee figure only up to Rs 4,00,000; from Rs 5,00,000 up it grants a room
*category* ("Single Standard A/C Room") with no rupee cap at all.

The insured's own policy schedule holds the missing number. So the audit accepts
it as an optional input.

**Leaving it blank is a valid answer.** When it is blank and the wording defers
the limit to the schedule, every room-rent-dependent line comes back flagged for
human review with the reason:

> room limit is set by the policy schedule, which was not provided

Not a default. Not an assumption. The alternative — picking a plausible limit —
would produce a confident number with nothing behind it, which is the failure
this system exists to avoid.

For Star Health at Rs 3,00,000 or Rs 4,00,000 the flow stays exactly as
intended: one upload, three dropdowns, no fourth field needed.

## Known assumptions

Some rules depend on facts no bill carries. Where that happens the audit makes
the assumption, states it in the report and records it in the trace with the
clause text that creates the problem. It is never hidden.

### Differential billing

Both Star Health and HDFC Ergo disapply proportionate deduction at hospitals
that do not bill differentially:

> **Proportionate deductions are not applied** in respect of the hospitals which
> do not follow differential billing, or for those expenses in respect of which
> differential billing is not adopted based on the room category.
> — Star Health, clause II.1

Nothing on a hospital bill says whether that hospital bills differentially, and
no input to this system could carry it. So:

- **Default: proportionate deduction fires.** The assumption is that the hospital does bill differentially.
- The assumption is **printed with every report** and stored in the trace alongside the clause that carries the carve-out, so a reader can see it was assumed rather than proven.
- Pass `--no-differential-billing` to turn it off.

A system that refused to audit any bill because it could not verify a hospital's
billing practice would be useless. Stating the assumption is honest; making it
silently is not.

## Running locally

```bash
uv sync
uv run python -m core.ingest                       # build the clause index (once)
uv run python -m core.audit data/sample_bill.txt --policy star_health --sum-insured 300000
uv run python -m core.audit data/sample_bill.txt --policy hdfc_ergo --sum-insured 500000 --room-limit 5000
uv run python -m core.audit data/sample_bill.txt --policy star_health --sum-insured 300000 --no-differential-billing
```

Requires [Ollama](https://ollama.com) running with `qwen3:8b` pulled.
