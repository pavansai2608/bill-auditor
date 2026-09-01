# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state (update this at the end of every phase)

**Last updated: 2026-09-01, Phase 7 code complete, v3 eval NOT yet run — see the blocker below.**

Built and passing:

- `core/` — config, llm (Ollama + disk cache), logging_conf, models, masking,
  bill, money, assumptions, splitter, ingest, retrieve, `audit.py` (the naive
  **v0** path), `agent.py` (the **v2** LangGraph retry loop), `second_pass.py`
  (the **v3** proportionate deduction, wired in as `audit_lines(..., second_pass=True)`
  and `evaluate.py --second-pass`).
- The clause index: 402 clauses in `data/clauses.json` (star_health 153,
  hdfc_ergo 144, niva_bupa 105) plus `non_payable.json`.
- The eval harness: **44 bills** in `eval/bills/`, an answer key derived
  straight from the PDFs by `eval/derive_key.py`, and `eval/evaluate.py`
  (`--agent` scores the loop, without it scores naive v0).
- 138 PyUnit tests, all passing.

Not built yet — do not assume these exist:

- `core/guardrails.py` — **NOT BUILT.** The guardrails that do exist
  live inline: **2** (fabricated citation) in `agent.grade()`, **5** (rerank
  score below threshold) in `agent.retrieve()`/`agent.judge()` and in
  `audit.py`, **7** (PII) in `core/masking.py`. There is no central module and
  not all 8 are implemented.
- `api/`, `frontend/`, `k8s/` — **empty scaffolding.** `api/` holds a single
  empty `__init__.py`; the FastAPI job-polling service described under Layout
  is a design, not code. `tests/e2e/` does not exist either.
- `CLAUDE_CODE_PROMPT_v2.md` is **not in the repo** — it is referenced below as
  the authoritative spec but is not present and is not gitignored.

Last recorded eval: **v2, line accuracy 51.2%** (v0 was 24.4%), citation
accuracy 33.3%, abstention recall 100%, dodges down 42 → 22, false answers 0,
p95 267.1s (`eval/results.md`, 10 bills, 82 lines).

**BLOCKER before v3 is run — the v2 row shows 18 fabricated clauses, and that
number is wrong.** All 18 are the non-payable fast path citing `IRDAI-List-I`,
which is what the answer key itself cites for those lines. `evaluate.py` builds
`valid_ids` from `data/clauses.json` only, so the IRDAI list — a real, checkable
source in `data/non_payable.json` — is counted as a fabrication. The v0 row
scored 0 only because v0 has no fast path. Fix the counter in `evaluate.py`
before recording v3, and re-run v2 so the row is truthful. Nothing in
`core/agent.py` fabricates: `grade()` rejects an unknown id and `abstain()`
sets `clause_id=None`.

A second, smaller eval bug: `_calls()` in `evaluate.py` patches
`core.audit.search`/`complete_structured`, but the agent path calls
`core.agent.search`/`complete_structured`, so "Avg tool calls per bill" reads
**0.0** on any `--agent` run. The metric is blind, not the loop.

### END OF EVERY PHASE — do these three, without being asked

1. Run the eval and record it:
   `uv run python eval/evaluate.py --quick --agent --version vN --write`
   (bump `N`; add `--second-pass` from Phase 7 onward).
2. Update this **Current state** block: what is built, what is not, and the
   latest version and score.
3. Output the four blocks — WHAT I DID / FILES CHANGED / GIT COMMANDS /
   VERIFY IT WORKED — and stop, so the repo owner runs the git commands.

**If the score DROPS from the previous version, stop and explain why before
starting the next phase.** Do not carry on past a regression;
`git bisect run python eval/evaluate.py --quick --threshold 0.80` finds the
commit that caused it.

## Working rules (non-negotiable)

1. **Never run a git command.** Not `add`, `commit`, `push`, `merge`, `tag`, `config`, `checkout` — none. The repo owner runs all of them. Output the exact commands as text under a `## GIT COMMANDS — run these yourself` heading instead.
2. **No AI attribution anywhere.** No `Co-Authored-By`, no "Generated with", no robot emoji, no mention of Claude/AI/an assistant in commit messages, PR bodies, code comments, or the README. This is a solo academic capstone.
3. **After every piece of work, output exactly four blocks:** `## WHAT I DID` (3–6 plain sentences), `## FILES CHANGED`, `## GIT COMMANDS — run these yourself`, `## VERIFY IT WORKED` (a command, the expected output, and what a wrong output means). Never skip the verify block.
4. **Stop at the end of each numbered phase** and wait to be told to continue.

The authoritative spec is `CLAUDE_CODE_PROMPT_v2.md` (the build prompt). Re-read it before starting a phase — but see Current state: that file is not in this repo, so ask for it rather than working from memory of it.

## Domain

Agentic RAG that audits Indian health insurance claim bills. A bill line is checked against a policy PDF's numbered clauses; the output is a line-by-line table where every deduction cites the clause that caused it, and lines with no clearly applicable clause are flagged rather than guessed at.

## Hard rules that shape the code

- **The LLM never does arithmetic.** `JudgeOutput` deliberately has no `allowed` field — the model returns a limit plus a `clause_id`, and Python multiplies/subtracts. 8B models are unreliable at maths, and a wrong total is invisible.
- **Every verdict must cite a `clause_id` present in `data/clauses.json`.** An ID not in the index means reject the verdict and retry. A fabricated citation is the worst failure this system can produce; the eval tracks it as a metric that must stay at 0.
- **`core/` imports no web framework.** Pure Python logic; `api/` calls into it.
- **`num_ctx=8192` on every Ollama call.** The default is 2048 and truncates retrieved clauses silently — no error, just confident nonsense. Set in `core/config.py`, applied in `core/llm.py`.
- **Every LLM call is cached to disk by prompt hash.** The eval is re-run 50+ times.
- **When confidence is low, `needs_human=True`.** Never guess.
- **Monolith through Phase 8.** Microservices only in Phase 10.

## Commands

```bash
uv sync                                   # install from uv.lock
uv run ruff check . && uv run ruff format .
uv run python -m unittest discover -s tests    # PyUnit, as Jenkins runs it
uv run python -m unittest tests.test_math      # a single test module
uv run python -m unittest tests.test_math.MathTest.test_room_rent   # a single test
uv run python eval/evaluate.py                 # full 44-bill eval, naive v0 path
uv run python eval/evaluate.py --agent --version v2 --write   # score the agent loop, append to results.md
uv run python eval/evaluate.py --quick --threshold 0.80   # CI gate; exit 1 below threshold
uv add <pkg>                              # then: uv export --format requirements-txt --no-hashes > requirements.txt
```

Tests are **PyUnit (`unittest`)**, not pytest — Jenkins drives them through PyBuilder (`pyb run_unit_tests`). `requirements.txt` is a generated export, never hand-edited.

Ollama must be running with `qwen3:8b` pulled for anything that touches the model.

## Architecture

Setup runs once, offline: policy PDFs → pdfplumber text → **custom regex splitter on clause numbers** (never a LangChain text splitter — character chunking loses the clause number and citation becomes impossible) → `data/clauses.json` checkpoint → bge-base embeddings in ChromaDB + an in-memory BM25 index over the same clauses.

Four things about the real PDFs that the splitter had to handle, each found the hard way:

- **star_health.pdf is two-column.** `extract_text()` reads straight across and interleaves the columns into nonsense. Columns are detected per document by what fraction of text lines *begin* in the right half (star ≈ 0.41, the single-column ones ≈ 0.02–0.04) and cropped separately. Word-overlap heuristics near the page centre do not separate these documents; line-start position does.
- **Clause numbers restart per section.** `1.1` is both "Standard Definitions" (Section A) and "Hospitalization Expenses" (Section B) in hdfc_ergo. IDs are therefore section-qualified — `A.1.1`, `B.1.1`, `II.11` — which is also how the documents cite themselves ("Section B-2.9").
- **Split before joining wrapped lines, never after.** Joining first glues a heading onto the sentence below it, the heading stops being its own line, and the clause vanishes from the splitter. This silently cut the yield to 88 clauses.
- **Definitions blocks need a second pass.** hdfc_ergo's "Standard Definitions" is one 16k-character clause with 60+ terms numbered `Def. N.` inside it. Left whole it swamps `num_ctx` and makes "Room Rent means…" uncitable, so it is split again on that numbering into `A.1.1.Def41`.

Numbered list items inside a clause (`1. it needs ongoing monitoring`) match the clause pattern too. They are rejected by requiring a heading to start with a capital or digit — a list item continues a sentence and starts lower-case.

Retrieval is four stages, not two. Dense (Chroma/bge-base, cosine) and BM25 run in parallel and are fused by `EnsembleRetriever` at 0.6/0.4 — the lexical channel exists because policy documents are full of terms that must match literally ("Aggregate Deductible", "Excl03", "Vasofix Safety") and embeddings blur exactly those. Then **long clauses are split into sentence windows before reranking**: Star Health states its per-day room rent table inside a 1,500-character "In-patient Treatment" clause, and scored whole the one relevant sentence is drowned. Each window carries its parent's `clause_id` so citations still resolve, and `ClauseReranker` collapses windows back to one per clause so the top 3 are three distinct clauses. Everything is filtered to a single policy — a citation from the wrong insurer is a fabricated citation.

Two things measured in Phase 3 that matter later:

- **The rerank score tracks query specificity, the ranking does not.** "higher room category pro-rata deduction" scores 0.58 against Niva Bupa; a fuller phrasing scores 0.98 — but clause 6.2.4 ranks first either way. Guardrail 5 keys off the score, so a vague query can cause a *false abstention*. That is the agent's problem to fix by rewriting, not the retriever's.
- **Niva Bupa has no per-day room rent cap at all.** ReAssure 2.0 caps by room *category* with a pro-rata rule (6.2.4). Querying it for a "limit per day" correctly returns low scores. Do not treat that as a retrieval bug.

### The optional 4th input: policy schedule

The UI's three dropdowns (insurer, sum insured, policy start date) are enough
for Star Health, whose wording carries a room rent table keyed on sum insured.
They are **not** enough for the other two:

- **HDFC Ergo** — "Room rent limit shall be *'At Actuals'* unless otherwise specified in the Policy Schedule" (B.1.1). No figure in the document.
- **Niva Bupa** — caps by room *category* "as specified in your Policy Schedule" (6.2.4), with the pro-rata formula `(Eligible Room Rent limit / Room Rent actually incurred) x Associated Medical Expenses`.

So there is a fourth input: **"room limit as per your policy schedule"**, blank
by default, carrying either a rupee per-day figure or a room category.

**Blank is a valid answer.** When it is blank and the wording defers the limit
to the schedule, every room-rent-dependent line returns `needs_human` with the
reason *"room limit is set by the policy schedule, which was not provided"* —
not a default, not a guess. `SCHEDULE_DEFERRAL_RE` in `core/audit.py` detects
the deferral; `PolicySchedule` in `core/models.py` carries the value.

This keeps the one-upload-three-dropdown flow intact for Star Health and makes
the other two auditable when the insured knows their own limit. Bills B43 and
B44 exist to test that the abstention actually happens rather than being
assumed.

### Tables are read structurally, never flattened

`extract_text()` reads straight across a table and interleaves the columns.
Star Health's room rent table came out as `...3,00,000/Up to 5,000/- per day
4,00,000/5,00,000/...` — with `5,00,000` sitting next to the limit that belongs
to 3L and 4L. A judge reading that picks the wrong row and sounds certain.

Table regions are therefore removed from the flowing text and re-inserted at
the same vertical position as one labelled line per row, marked `[table]`:

```
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
```

Four details that matter, each found the hard way:

- **Cell geometry, not forward-fill alone.** A merged cell is one tall cell covering several rows; each row takes the cell whose vertical span contains its midpoint. Forward-fill then handles what is left.
- **Word centres, not crops.** Cropping a cell catches the tail of the line above, putting `2,00,000/- 3,00,000/-` in one cell.
- **The header band.** Star Health rules its table from the second row down, so the header and the first data row sit outside the detected table. The 48pt band above is read as part of it, filtered to lines that look like labels.
- **A data-table guard** (`is_data_table`). `find_tables()` also fires on prose layout boxes; without the guard, clause headings inside them are swallowed — this cost 97 clauses.

### Limits are a list, not three fields

`JudgeOutput.limits` is `list[Limit]`, each with its own `basis` (`per_day`,
`per_hospitalization`, `per_policy_period`, `absolute`) and either a rupee
`amount` or a `percentage` of sum insured. `money.allowed_for_line` resolves
every limit to rupees for the bill in hand and takes the **minimum**.

Three separate fields could not hold what the wording says. `star_health II.8`
states two limits in one sentence — "Rs.750/- per hospitalization **and**
Rs.1,500/- per Policy Period" — and several benefits read "10% of Sum Insured
**or** Rs 1,00,000, whichever is less" (`II.11`, `II.19`, `II.27`). With one
field the model had to discard one limit silently. One list plus a minimum
handles both shapes through the same code path, and the model still only
reports what it read.

`over_limit` is set only by a breached **per-day** cap, because that is what
triggers the proportionate-deduction second pass; an absolute cap reduces one
line and nothing else.

### The table code is frozen by golden files

`tests/test_tables_golden.py` stores the exact extracted text of the eight
rule-bearing table clauses under `tests/fixtures/tables/`, and fails on any
diff. It splits straight from the PDFs, so it tests the splitter rather than
the checkpoint.

It exists because this code broke three times and **every break was silent** —
the output still looked like text, so nothing failed and the damage only showed
when someone read a clause by eye. One of those breaks put `5,00,000` next to a
limit belonging to the 3L and 4L rows.

If a change to the splitter is intended, regenerate deliberately:

```bash
uv run python tests/test_tables_golden.py --update
```

Read the diff before you do. Regenerating without reading it is how the fourth
regression gets in.

### Cross-references travel with the clause

`Clause.refs` holds clause ids a clause names, extracted at ingest
(`find_refs`, plus an IRDAI exclusion-code index so "Code Excl 02" resolves to
the clause that defines it). `retrieve.with_references` pulls those clauses in
alongside the parent.

This exists because `star_health II.28` applies co-payment only to "Coverages
II.1, II.2, … II.13" — retrieving it without that list invites applying a 20%
cut to a line it does not cover — and `II.19` disapplies three exclusions by
code.

**It is deliberately the cheap half.** A reference stated in prose is not
caught: `III.2` says *"the longer of the two waiting periods shall apply"*,
naming the PED period in words with no id to match. Fixing that needs the judge
to be able to say *"I need another clause, and here is which one"* — which is
the motivation for the Phase 6 agent loop, not something to bolt onto retrieval.

Per request, each bill line runs through a LangGraph loop: non-payable fast path (zero LLM calls) → classify rule type → build query → hybrid retrieve (Chroma 20 + BM25 20 via EnsembleRetriever, 0.6/0.4) → cross-encoder rerank to top 3 → LLM judge → guardrails → **Python computes the amount**. On low confidence the query is rewritten from a different angle and retried, capped at 3 attempts and 8 tool calls, then abstains.

**The second pass is the point of the project — and it is NOT BUILT YET (Phase 7).** What follows is the design, not a description of code that exists.

 After all lines are judged, if any line breached its room-rent limit, a proportionate-deduction clause is retrieved and its ratio applied to every other eligible line. Judging lines independently can never find this — nothing in the surgeon's-fee line mentions room rent, yet one breached limit silently rewrites every other line.

### Layout

- `core/` — `config.py` (all settings, `BA_` env prefix) · `llm.py` (Ollama + sha256 disk cache) · `logging_conf.py` (logging + JSONL `TraceWriter`) · `models.py` (Pydantic contracts) · `masking.py` (PII stripped before any prompt) · `bill.py` (text → validated `BillLine`s) · `money.py` (all arithmetic) · `assumptions.py` (differential billing, stated not hidden) · then `splitter.py`, `ingest.py`, `retrieve.py`, `audit.py` (naive v0), `agent.py` (the loop). `second_pass.py` and `guardrails.py` are **planned for Phase 7 and do not exist**.
- `api/` — **empty (`__init__.py` only).** Planned: FastAPI, and because audits take 30–60s, `POST /audit` returns a `job_id` immediately and the client polls `GET /audit/{job_id}`, with an in-memory job dict and no database.
- `frontend/`, `k8s/` — **empty directories.** The UI is a later phase; `k8s/` is Phase 10.
- `eval/` — deterministic metrics only, no LLM judge. 44 bills; `derive_key.py` builds the answer key from the PDFs alone (it imports no retriever, judge or audit code, so a pipeline bug cannot score itself as a success). `results.md` holds the v0→v4 table and is the project's headline result.
- `tests/` — PyUnit, 122 tests. `tests/e2e/` (Selenium 4) is planned and **does not exist yet**; `tests/fixtures/tables/` holds the golden table files.
- `data/` — `clauses.json` and `non_payable.json` are committed checkpoints; `db/`, `llm_cache/`, `policies/*.pdf` are gitignored.
- `src/bill_auditor/` — packaged console script. Note `core/` and `api/` live outside `src/` and are import-path-only.

## Git workflow

GitFlow: `main` (tagged releases only) ← `release/vX` ← `develop` ← `feature/short-name`. Commits are Conventional Commits: `feat(agent): add retry loop with query rewriting`. The `.githooks/commit-msg` hook enforces the format and a 72-character subject limit; `.githooks/pre-commit` runs ruff. Install with `git config core.hooksPath .githooks`.

**No issue tracker.** This is a solo project, so the `[BA-XX]` ticket IDs the original spec called for have been dropped. Commits before `262e6eb` still carry them — that history is not rewritten. Do not add ticket IDs to new commits.

**Always branch from `develop`.** Running `git checkout -b feature/next` while still standing on the previous feature branch stacks them, and `develop` then holds none of the work — which has already happened once here. `git checkout develop` first, every time.

Annotated tags mark eval milestones: `v0` naive baseline · `v1` hybrid retrieval · `v2` agent loop · `v3` second pass · `v4` all 8 guardrails · `v1.0.0` submission.

When eval accuracy drops between tags, `git bisect run python eval/evaluate.py --quick --threshold 0.80` finds the commit — surface this whenever a drop is recorded in `results.md`.

## Do not add

SQLite, Redis, Celery, Ragas, Langfuse, any paid API, authentication, or a database. LangChain text splitters on policy documents.
