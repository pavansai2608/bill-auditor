# CLAUDE.md

Operating rules for working in this repository. The engineering record - why the
splitter, the retrieval, the guardrails and the pipeline are built the way they
are - is `ENGINEERING.md`. The phase plan is `PHASES.md`.

## Current state (update this at the end of every phase)

**Last updated: 2026-09-06. Every phase in `PHASES.md` is built, including
Jenkins. The recorded eval is `v11` at 55.2% line accuracy over all 44 bills.
The CI gate runs the 10-bill subset against a 56.1% baseline at
`--threshold 0.52`. 462 tests.**

**Read `KNOWN_LIMITATIONS.md` sections 6 and 7 before quoting any accuracy
number**, and treat `eval/results.md` as the only authoritative source for one.
The analysis behind the current figure - what moved between versions, where the
remaining errors are, and why the version ladder must not be joined to the
headline - is in `ENGINEERING.md`.

Built and passing:

- `core/` — config, llm (Ollama + disk cache), logging_conf, models, masking,
  bill, money, assumptions, splitter, ingest, retrieve, `audit.py` (the naive
  **v0** path), `agent.py` (the **v2** LangGraph retry loop), `second_pass.py`
  (the **v3** proportionate deduction, wired in as `audit_lines(..., second_pass=True)`
  and `evaluate.py --second-pass`), `room_limit.py` (the **v4** deterministic
  room rent lookup - policy + sum insured reads the table row directly, with no
  judge call; the agent's `room_limit` node is path B beside the non-payable
  fast path), `waiting.py` (the **v5** waiting periods - two dates and the
  period the clause states, decided before any line is judged; a bill inside a
  waiting period costs zero model calls).
- `api/` — FastAPI (Phase 8). `POST /audit` and `POST /compare` return a
  `job_id` immediately and run in a `BackgroundTasks` worker; `GET
  /audit/{job_id}` reports `done`/`total` until the report lands. In-memory job
  store, no database. `POST /policies/upload` indexes a user's own PDF.
- `frontend/` — React + TypeScript + Vite (Phase 9), with the design tokens in
  `frontend/design/`. `useAuditJob` owns the polling; the report screen is
  loaded with `React.lazy`.
- `services/` — the same `core/` split into four containers (Phase 10):
  retrieval, audit, ingestion, gateway. `api/` remains a working monolith for
  local development and the eval; see D-10.
- Docker, `k8s/`, `build.py` and `Jenkinsfile` (Phase 11). The Jenkins Eval
  stage fails the build below `--threshold 0.52` on the 10-bill subset. The
  pipeline records each gate as it passes and Docker, Deploy and Prune refuse to
  run unless every earlier gate actually ran - see the gate ledger in
  `ENGINEERING.md`. `k8s/deploy.sh` loads this build's images into minikube,
  rolls out the BUILD_NUMBER tag and fails if any pod is not on it;
  `ci/prune_images.py` then deletes stale tags, keeping N, N-1, `latest` and
  anything the cluster is live on.
- The clause index: 402 clauses in `data/clauses.json` (star_health 153,
  hdfc_ergo 144, niva_bupa 105) plus `non_payable.json`.
- The eval harness: **44 bills** in `eval/bills/`, an answer key derived
  straight from the PDFs by `eval/derive_key.py`, and `eval/evaluate.py`
  (`--agent` scores the loop, without it scores naive v0).
  `eval/make_text_bills.py` writes each bill out as pasteable text under
  `eval/bills/text/` with an `INDEX.md` of the form inputs, and checks the
  `bill_text` and the `lines` array of every bill against each other — the two
  halves of a fixture can drift and nothing else compares them. `--llm` runs
  the same check through `core.bill.parse_bill` instead of the regex.
- 462 PyUnit tests, all passing, `unittest discover -s tests` in ~80s.

Not built yet — do not assume these exist:

- `core/guardrails.py` — **NOT BUILT.** The guardrails that do exist
  live inline: **2** (fabricated citation) in `agent.grade()`, **5** (rerank
  score below threshold) in `agent.retrieve()`/`agent.judge()` and in
  `audit.py`, **7** (PII) in `core/masking.py`. There is no central module and
  not all 8 are implemented.
- Nothing from `PHASES.md` is unbuilt. What is *unverified* is in
  `BLOCKED.md`. **Kubernetes is no longer unverified** - as of 2026-09-03 every
  pod reaches `1/1 Running` on minikube and `rollout status deploy/gateway`
  exits 0. Getting there found three defects: the Docker stage built
  `bill-auditor/gateway-service` while the manifest asks for
  `bill-auditor/gateway`; minikube runs its own Docker daemon so images built
  into Docker Desktop are invisible to it and must be `minikube image load`ed;
  and ollama's 6Gi request left no room for two replicas of audit and retrieval,
  so both are now one. See B-01. **Docker is no longer unverified** — as of 2026-09-01 all
  five images build, all six containers report healthy and B01 was audited end
  to end through the gateway. Running it found four defects that syntax
  checking could not: the four Python images could not build at all (`-e .` in
  `requirements.txt` with no `src/` in the builder stage), ingestion had no
  Ollama URL so all 402 clauses were labelled `other`, the frontend
  healthcheck probed `localhost` against an IPv4-only nginx, and `qwen3:8b`
  was OOM-killed in a 7.7 GB VM. See B-02.

## END OF EVERY PHASE — do these three, without being asked

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

The phase plan is `PHASES.md`. Re-read it before starting a phase. (It replaces `CLAUDE_CODE_PROMPT_v2.md`, which the original spec referenced but which was never committed.)

## Commands

```bash
uv sync                                   # install from uv.lock
uv run ruff check . && uv run ruff format .
uv run python -m unittest discover -s tests    # PyUnit, as Jenkins runs it
uv run python -m unittest tests.test_math      # a single test module
uv run python -m unittest tests.test_math.MathTest.test_room_rent   # a single test
uv run uvicorn api.main:app --reload           # API on :8000, docs at /docs
uv run python eval/evaluate.py                 # full 44-bill eval, naive v0 path
uv run python eval/evaluate.py --agent --version v2 --write   # score the agent loop, append to results.md
uv run python eval/evaluate.py --quick --threshold 0.80   # CI gate; exit 1 below threshold
uv add <pkg>                              # then: uv export --format requirements-txt --no-hashes > requirements.txt
```

Tests are **PyUnit (`unittest`)**, not pytest — Jenkins drives them through PyBuilder (`pyb run_unit_tests`). `requirements.txt` is a generated export, never hand-edited.

Ollama must be running with `qwen3:8b` pulled for anything that touches the model.

## Git workflow

GitFlow: `main` (tagged releases only) ← `release/vX` ← `develop` ← `feature/short-name`. Commits are Conventional Commits: `feat(agent): add retry loop with query rewriting`. The `.githooks/commit-msg` hook enforces the format and a 72-character subject limit; `.githooks/pre-commit` runs ruff. Install with `git config core.hooksPath .githooks`.

**Every commit carries a `[BA-XX]` ticket**, at the end of the subject, enforced by `.githooks/commit-msg` — install it with `git config core.hooksPath .githooks` or it does nothing. Numbering is continuous across the whole history; find the next free number with `git log --all --format=%s | grep -o '\[BA-[0-9]*\]'`. See D-01.

**Always branch from `develop`.** Running `git checkout -b feature/next` while still standing on the previous feature branch stacks them, and `develop` then holds none of the work — which has already happened once here. `git checkout develop` first, every time.

Annotated tags mark eval milestones: `v0` naive baseline · `v1` hybrid retrieval · `v2` agent loop · `v3` second pass · `v4` all 8 guardrails · `v1.0.0` submission.

When eval accuracy drops between tags, `git bisect run python eval/evaluate.py --quick --threshold 0.80` finds the commit — surface this whenever a drop is recorded in `results.md`.

## Do not add

SQLite, Redis, Celery, Ragas, Langfuse, any paid API, authentication, or a database. LangChain text splitters on policy documents.
