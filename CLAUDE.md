# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working rules (non-negotiable)

1. **Never run a git command.** Not `add`, `commit`, `push`, `merge`, `tag`, `config`, `checkout` — none. The repo owner runs all of them. Output the exact commands as text under a `## GIT COMMANDS — run these yourself` heading instead.
2. **No AI attribution anywhere.** No `Co-Authored-By`, no "Generated with", no robot emoji, no mention of Claude/AI/an assistant in commit messages, PR bodies, code comments, or the README. This is a solo academic capstone.
3. **After every piece of work, output exactly four blocks:** `## WHAT I DID` (3–6 plain sentences), `## FILES CHANGED`, `## GIT COMMANDS — run these yourself`, `## VERIFY IT WORKED` (a command, the expected output, and what a wrong output means). Never skip the verify block.
4. **Stop at the end of each numbered phase** and wait to be told to continue.

The authoritative spec is `CLAUDE_CODE_PROMPT_v2.md` (the build prompt). Re-read it before starting a phase.

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
uv run python eval/evaluate.py                 # full 40-bill eval
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

Per request, each bill line runs through a LangGraph loop: non-payable fast path (zero LLM calls) → classify rule type → build query → hybrid retrieve (Chroma 20 + BM25 20 via EnsembleRetriever, 0.6/0.4) → cross-encoder rerank to top 3 → LLM judge → guardrails → **Python computes the amount**. On low confidence the query is rewritten from a different angle and retried, capped at 3 attempts and 8 tool calls, then abstains.

**The second pass is the point of the project.** After all lines are judged, if any line breached its room-rent limit, a proportionate-deduction clause is retrieved and its ratio applied to every other eligible line. Judging lines independently can never find this — nothing in the surgeon's-fee line mentions room rent, yet one breached limit silently rewrites every other line.

### Layout

- `core/` — `config.py` (all settings, `BA_` env prefix) · `llm.py` (Ollama + sha256 disk cache) · `logging_conf.py` (logging + JSONL `TraceWriter`) · `models.py` (Pydantic contracts) · then `splitter.py`, `ingest.py`, `retrieve.py`, `agent.py`, `second_pass.py`, `guardrails.py`, `audit.py`
- `api/` — FastAPI. Audits take 30–60s, so `POST /audit` returns a `job_id` immediately and the client polls `GET /audit/{job_id}`. In-memory job dict, no database.
- `eval/` — deterministic metrics only, no LLM judge. `results.md` holds the v0→v4 table and is the project's headline result.
- `tests/` — PyUnit; `tests/e2e/` is Selenium 4.
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
