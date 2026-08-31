## Ticket

BA-

## What changed

<!-- One paragraph. What problem does this solve? -->

## Why

<!-- The reasoning, not the diff. Reviewers can read the diff. -->

## Evaluation impact

<!-- Fill in if this touches ingest, retrieve, agent, second_pass or guardrails. -->

| Metric | Before | After |
|---|---|---|
| Line accuracy | | |
| Clause accuracy | | |
| Payout error | | |
| Fabricated clauses | 0 | 0 |

- [ ] Fabricated clause count is still 0
- [ ] `eval/results.md` updated if a milestone was reached

## Checklist

- [ ] Branch is `feature/BA-XX-*`, `release/vX` or `hotfix/BA-XX-*`
- [ ] Every commit subject carries `[BA-XX]`
- [ ] `uv run ruff check .` passes
- [ ] `uv run python -m unittest discover -s tests` passes
- [ ] No arithmetic performed by the LLM
- [ ] `core/` still imports no web framework
- [ ] No secrets; `.env.example` updated if a new setting was added

## How to verify

<!-- Exact command a reviewer runs, and what they should see. -->
