# PHASES.md — the authoritative spec for this project

This file replaces `CLAUDE_CODE_PROMPT_v2.md`, which was never committed to the
repo. `CLAUDE.md` must point here.

**Read this file in full before doing anything.** If your context was lost and you
are picking this project up cold, this file plus `CLAUDE.md`, `README.md`,
`eval/results.md` and `KNOWN_LIMITATIONS.md` are enough to continue without asking.

---

# PART 0 — WORKING RULES (never violated)

## 0.1 Git

**Never run a git command.** Not `git status`, not `git diff`, not `git log`.
Output them as text.

**I am doing every commit myself, once, at the very end.** Nothing will be
committed while you work. Everything you write simply sits in the working tree
until I return and run the whole thing in one go. Plan for that:

- **`GIT_COMMANDS.md` is a single script I will run top to bottom.** Append to it
  as you finish each phase, under a heading for that phase, in the exact order the
  commands must run. Do not scatter commands across other files or rely on me
  remembering anything from your replies.
- **Every command must still be valid when run long after the files were written.**
  All the files already exist on disk by then, so each block is: create the branch,
  `git add` only that phase's files, commit, and merge. Never `git add .` — it
  would sweep a later phase's files into an earlier commit and the history would
  be a lie.
- **Assume nothing about the starting state** beyond what is already recorded in
  `CLAUDE.md`. Begin the file with a short "before you start" block: which branch
  I should be on, and a `git status` for me to eyeball.
- **Put a checkpoint between phases** — a comment line saying what should be true
  at that point (which branch, which tag exists, how many commits) so I can tell
  where I am if I stop halfway.
- **Say what each block does and why**, one comment line above it. When I run this
  I will have forgotten the details.
- **Nothing you build may depend on a commit having happened.** No hook, script,
  test or pipeline step may assume a clean tree, a tag, or a branch that only
  exists after I run the file.
- The advanced git operations in Part 4 still have to appear in the history. Since
  they will all be run at the end, sequence them so they are honest: the revert
  reverts something that was really committed a few commits earlier, the
  cherry-pick takes a commit that really exists on the branch it names. Do not
  invent a fake sequence just to tick the box — if an operation has no honest
  place, say so in `DECISIONS.md` and leave it out.

Also print each phase's commands in your reply, so they exist in two places.

## 0.2 No AI attribution, anywhere

No `Co-Authored-By`. No "Generated with". No robot emoji. No mention of Claude,
AI, an assistant, or a model having written anything — not in commit messages,
code comments, docstrings, PR bodies, the README, or any documentation file. The
repository must read as the work of one developer.

This applies to the LLM the *product* uses as well: describing Qwen3 as the
judge model is correct and expected. Describing the *code* as AI-written is not.

## 0.3 Output format — every phase, without exception

**WHAT I DID** — plain language. Assume the reader is a 4th-year BTech student,
not a systems engineer. Short sentences. Say what the code now does, not how
clever it is.

**FILES CHANGED** — created / modified / deleted, one per line.

**GIT COMMANDS** — for me to run. Also appended to `GIT_COMMANDS.md`.

**VERIFY IT WORKED** — the exact command, the expected output, and what a
specific failure would mean. Not "check it works" — name the test class and say
what its failure implies about the system.

## 0.4 Autonomous operation

I am away and cannot answer questions. So:

- **Do not wait for me between phases.** Finish a phase, write its four blocks
  into `PROGRESS.md`, then start the next one.
- **When you need a decision I would normally make, make it**, then record it in
  `DECISIONS.md` with: what the choice was, what you picked, why, and what would
  have to be true for the other option to be better. Keep going.
- **If you are genuinely blocked** — something needs a credential, a running
  cluster, a paid service, or a file that does not exist — write it to
  `BLOCKED.md` with exactly what you need from me, **skip that item, and carry on
  with everything else in the phase.** Never stall the whole build on one blocked
  item.
- Prefer the boring, reversible choice. If in doubt, do the smaller thing and
  note the larger option in `DECISIONS.md`.

## 0.5 Things you must never do to the evaluation

The evaluation is the point of this project. It is easy to make the numbers look
better dishonestly, so:

- **Never edit `eval/answer_key.json`** to match what the system produced.
- **Never loosen a metric, a tolerance, or a threshold** to make a number pass.
- **Never delete a recorded row** from `eval/results.md`. If a row was wrong,
  mark it withdrawn and say why, next to the corrected one.
- **Never change what counts as a fabricated citation.** That metric must stay
  at 0 and must stay strictly defined.
- If a change makes a score **drop**, do not hide it. Record the drop, diagnose
  it in `PROGRESS.md`, and either fix it or write it into `KNOWN_LIMITATIONS.md`
  before moving on.

## 0.6 End of every phase

1. If the phase touched audit logic, run:
   `uv run python eval/evaluate.py --quick --agent --second-pass --version vN --write`
2. Update the **Current state** block in `CLAUDE.md`: what is built, what is not,
   latest version and score, and which phase is next.
3. Append the four blocks to `PROGRESS.md`.
4. Append the git commands to `GIT_COMMANDS.md`.
5. Run the full test suite. It must pass before you start the next phase. If it
   does not, fix it before moving on — a failing suite carried into the next
   phase makes every later failure ambiguous.

---

# PART 1 — WHAT THIS PROJECT IS

An **insurance bill overcharge auditor**. A patient uploads a hospital bill and
picks their insurance policy. The system reads every line of the bill, checks it
against that policy's rules, and reports what the insurer will actually pay —
with the exact clause that caused each deduction.

The five rule types it handles:

| Rule | Example |
|---|---|
| room_rent | Rs 5,000/day cap; exceeding it triggers proportionate deduction |
| non_payable | Gloves, syringes, admission charges — never covered |
| sub_limit | Ambulance capped at Rs 750 per hospitalisation |
| copay | The insured pays a fixed percentage |
| waiting_period | Condition not covered until N months after the policy started |

Anything outside these five returns `needs_human`. That is correct behaviour,
not a gap.

**The hard rule of the whole system:** the LLM never does arithmetic. It reads a
clause and reports a limit plus a `clause_id`. Python does every multiplication,
comparison and total. A verdict citing a `clause_id` that does not exist in the
index is rejected outright.

**Users:** three built-in policies (Star Health, HDFC Ergo, Niva Bupa) plus an
"upload my own policy" path.

---

# PART 2 — CURRENT STATE AT THE TIME THIS FILE WAS WRITTEN

Phases 1-7 are complete plus two accuracy passes. 185 tests pass.

| Version | What was added | Line accuracy |
|---|---|---|
| v0 | Naive: one search, one judge call, no retry | 24.4% |
| v2 | LangGraph agent loop with retry on low confidence | 51.2% |
| v3 | Proportionate-deduction second pass | 54.9% |
| v4 | Room limit read from the table, not the model | 59.8% |
| v5 | Waiting periods decided from dates, not the model | 68.3% |

Fabricated clauses: **0 at every version.** That must never change.

Built: `core/` (splitter, ingest, retrieve, agent, audit, money, masking,
second_pass, room_limit, waiting, assumptions, models, config, llm),
`eval/` (44 bills, a hand-derived answer key, evaluate.py, helper.py,
results.md, verify_clauses.md), `tests/` (185 tests), `KNOWN_LIMITATIONS.md`.

Not built: `api/` is an empty `__init__.py`. `frontend/` and `k8s/` are empty.
No Dockerfiles, no Jenkinsfile, no build.py.

Known open issues, already documented, **do not treat as bugs to fix**:
sub_limit accuracy is 0% because the loop cannot distinguish "there is no cap"
from "the search missed the cap"; Star Health's specified-disease list did not
survive extraction; the PED rule is unimplemented.

---

# PART 3 — TECH STACK (do not substitute)

**Backend:** Python 3.14, FastAPI, Pydantic v2, pydantic-settings, uv.
**RAG:** LangChain, LangGraph, ChromaDB (cosine), rank-bm25,
sentence-transformers (`BAAI/bge-base-en-v1.5` embeddings,
`BAAI/bge-reranker-base` cross-encoder).
**LLM:** Ollama running `qwen3:8b`, `num_ctx=8192`, `temperature=0`,
`keep_alive="30m"`. A hash-keyed disk cache under `data/llm_cache`.
**PDF:** pdfplumber. Tables via `extract_tables()`, never `extract_text()` alone.
**Frontend:** React + TypeScript + React Query.
**Testing:** PyUnit (`unittest`), Selenium 4.
**Build:** PyBuilder (`pyb`). **CI:** Jenkins. **Containers:** Docker,
docker-compose, Kubernetes on minikube.
**Lint:** ruff.

Do not add: Redis, Celery, SQLite, a database of any kind, authentication,
user accounts, Ragas, Langfuse, or any paid service.

---

# PART 4 — GIT CONVENTIONS

**GitFlow.** `main` <- `develop` <- `feature/*`. Never commit directly to `main`.

**Conventional Commits with a ticket in every message:**

```
feat(api): add background job polling [BA-21]
fix(retrieve): stop reranking below the score threshold [BA-22]
docs(readme): lead with the results table [BA-23]
test(e2e): add Selenium flow for the compare screen [BA-24]
chore(docker): mount the model as a volume [BA-25]
```

Continue the `BA-XX` numbering from wherever the repo currently is. Never reuse
a number.

**Advanced git operations that must appear in the history before the project is
done.** Where a phase gives a natural opportunity, use it and say in the WHAT I
DID block that you did:

| Operation | Where it fits naturally |
|---|---|
| `git rebase -i` (squash) | Tidying a feature branch before merging |
| `git cherry-pick` | Taking one fix from a feature branch onto develop |
| `git revert` | Undoing a change that made a score drop |
| `git tag -a` | Every version, v0 through v5, plus v1.0.0 at the end |
| `git merge --no-ff` | Every feature branch into develop |
| `git stash` | Parking work to check something on another branch |
| `git bisect` | Finding the commit that dropped an eval score |
| `git worktree` | Working on two branches at once |
| `.gitattributes` | Already present; keep it correct |
| Git hooks | Already present in `.githooks`; keep the ticket check working |

Since I run the commands, put them in `GIT_COMMANDS.md` with a one-line comment
above each block saying what it does and why.

---

# PART 5 — PHASE 8: API

FastAPI in `api/`. **An audit takes 30-60 seconds. Never block the request.**

```
GET  /health                   -> {"status":"ok"}
GET  /policies                 -> list for the dropdown, with sum-insured
                                  options each policy actually supports
POST /audit                    -> {"job_id":"abc123"}, returns immediately
GET  /audit/{job_id}           -> {"status":"running","done":3,"total":7}
                               -> {"status":"done","report":{...}}
                               -> {"status":"failed","error":"..."}
POST /compare                  -> same job pattern, one bill against 3 policies
POST /policies/upload          -> index a user's own policy PDF, return its id
```

**`POST /audit` accepts:** bill as an uploaded file or pasted text, `policy`,
`sum_insured`, `policy_start_date`, `admission_date`, and optional
`room_limit_per_day` / `room_category` from the policy schedule.

**The report returned must include** the line-by-line verdicts, the totals, the
per-line trace, and the **ASSUMPTIONS** block. A user has to be able to see that
differential billing was assumed rather than proven.

Implementation notes:
- `BackgroundTasks` plus a module-level job dict. No database.
- The job dict grows forever; cap it at the 100 most recent jobs and evict oldest.
- CORS enabled for `http://localhost:5173` and `http://localhost:3000`.
- Reuse the Pydantic models in `core/models.py`. Do not define parallel ones.
- A failed audit must set `status: failed` with a readable message, never hang
  in `running` forever.
- PII masking happens before anything is stored in the job dict, same as the CLI.

**Verify:** `/docs` renders every endpoint. `tests/test_api.py` covers: health,
policies list, an audit polled from running to done, a compare job, a bad
`sum_insured` rejected by Pydantic with 422, and a failed job reporting `failed`.

---

# PART 6 — PHASE 9: FRONTEND

React + TypeScript + React Query in `frontend/`. Vite.

**Screen 1 — Input**
- Bill: file upload or paste into a textarea
- Policy dropdown: the three built-ins + "upload my own"
- Sum insured dropdown: 3L / 5L / 10L / 25L
- Policy start date, admission date
- Optional: "room limit as per your policy schedule" — blank is valid and
  produces an honest `needs_human`, so label it clearly as optional
- "Audit this bill"

**Screen 2 — Report**
- Summary: total charged, total payable, number of lines flagged
- Line-by-line table: item, charged, allowed, the clause cited, the reason
- A collapsible trace per row showing how that line was decided
- The assumptions block, visible, not hidden behind a toggle
- "Compare with other policies"
- Download CSV

**Required React features** (they are on my syllabus, do not skip them):
a custom `useAuditJob` hook that owns the polling, Context for app state,
error boundaries, code splitting with `React.lazy`, React Query for the polling.

Polling: every 2 seconds, stop on done or failed, show progress from
`done`/`total`, and give up with a readable message after 5 minutes.

**Verify:** Selenium 4 E2E test in `tests/e2e/test_flow.py` — load the page,
fill the form, submit, poll until the report appears, assert a specific payable
figure. Use Selenium 4 specifically: relative locators (`above()`, `below()`,
`near()`), the new window/tab API, and explicit waits. No `time.sleep`.

The E2E test needs the API running. Write `tests/e2e/README.md` saying exactly
how to start both, and make the test skip with a clear message rather than fail
when the API is not up.

---

# PART 7 — PHASE 10: MICROSERVICES

Split the monolith. Six containers.

| Service | Owns | Calls |
|---|---|---|
| ingestion-service | PDF -> clauses -> embeddings | Chroma |
| retrieval-service | hybrid search + rerank | Chroma, BM25 |
| audit-service | agent loop, second pass, guardrails | retrieval-service, Ollama |
| gateway | routes, aggregates, the public API | audit, ingestion |
| ollama | the judge model | — |
| frontend | React build served by nginx | gateway |

Only `gateway` and `frontend` are exposed. The three inner services are reachable
only from inside the compose network.

Keep `core/` as a shared library the services import. Do not duplicate logic
across services.

Each service gets a `/health` endpoint. The gateway's `/health` reports the
health of its dependencies, so one command tells me what is down.

**Record in the README, for the viva:** ingestion is heavy but rare, retrieval is
light and frequent, audit is slow and CPU-bound. They scale differently, which is
why they are separate.

---

# PART 8 — PHASE 11: DEVOPS

## Docker

A `Dockerfile` per service plus `docker-compose.yml` for all six.

- **Mount the Ollama model as a volume. Never bake it into an image.** A 5 GB
  model in a layer means every rebuild re-downloads it.
- Multi-stage builds. Python services on a slim base, frontend built then served
  by nginx.
- `.dockerignore` excluding `.venv`, `data/db`, `data/llm_cache`, `__pycache__`,
  `node_modules`.
- Healthchecks in compose so `docker-compose up` reports honestly.
- Give me the exact commands to build, run, view logs and tear down.

## Kubernetes

`k8s/` targeting minikube:
- A Deployment and a Service per component
- A ConfigMap for settings, a Secret template for anything sensitive
- Resource requests and limits — audit-service needs the most
- Liveness and readiness probes on `/health`
- A PersistentVolumeClaim for the Ollama model
- **The LLM backend switchable by env var**, so a cluster can point at a hosted
  model instead of running an 8B model in a pod

Give me the exact commands: `minikube start` with enough memory, `kubectl apply`,
how to reach the gateway, how to read logs, how to tear down.

## PyBuilder

`build.py` with plugins `python.unittest`, `python.flake8`, `python.coverage`,
`python.distutils`. Jenkins calls `pyb`, never pytest directly. Coverage
threshold set to whatever the suite currently achieves, rounded down — not an
aspirational number that fails on day one.

## Jenkins

A `Jenkinsfile` for a multibranch pipeline:

```groovy
pipeline {
  stages {
    stage('Build')   { steps { sh 'pyb clean' } }
    stage('Quality') { parallel {
        stage('Lint') { steps { sh 'pyb analyze' } }
        stage('Unit') { steps { sh 'pyb run_unit_tests' } }
    }}
    stage('Eval')    { steps { sh 'python eval/evaluate.py --quick --threshold 0.65' } }
    stage('E2E')     { steps { sh 'python -m unittest tests.e2e.test_flow' } }
    stage('Docker')  { steps { sh 'docker build ...' } }
    stage('Deploy')  { steps { sh 'kubectl apply -f k8s/' } }
  }
  post { always { archiveArtifacts 'eval/results.md' } }
}
```

- `feature/*` runs Build + Quality
- `develop` adds Eval + E2E
- `main` adds Docker + Deploy
- **The Eval stage must fail the build when line accuracy drops below the
  threshold.** Set the threshold just under the current recorded score. This is
  the most distinctive part of the pipeline — say so in the README.

**Also write `JENKINS_SETUP.md`.** Assume I have never opened Jenkins. Cover:
installing it, which plugins, creating the multibranch pipeline job, pointing it
at the GitHub repo, adding credentials, where to see a failed stage's log, and
what to do when the Eval stage fails. Numbered steps, no assumed knowledge.

---

# PART 9 — README (write it in Phase 11)

Numbers first. Code last.

```
# Bill Auditor
[architecture diagram]

## Results
<the v0 -> v5 table — the first thing on the page>

## The problem
One worked example with real rupee figures, from bill to payable amount,
plus two concrete cases the system gets wrong

## How it works
The agent loop, and why each step exists

## How it decides when to stop
Stopping rules, the abstention policy, the guardrails, and the rule that a
verdict citing an unknown clause is thrown away

## Known assumptions
Differential billing is assumed, not verified, and why. Anything else assumed.

## Evaluation
How the 44 bills and the answer key were built. The answer key was derived by
reading the policy documents directly rather than by running the pipeline;
10 of 44 bills were verified manually against the source PDFs. Category
breakdown. Why the metrics are deterministic.

## Architecture
The services and why they are split that way

## CI/CD
The pipeline, and why the Eval stage can fail a build

## What I learned
3-4 specific findings. Candidates from this build:
 - a PDF table flattened into text silently corrupts every rupee limit
   downstream, and nothing errors
 - the room limit and waiting periods both got better by removing the model
   from the decision, not by prompting it harder
 - a scoring bug made 18 correct citations look like fabrications, which is
   why the metric now has its own test

## Where it still fails
3-4 honest examples with diagnosis, from KNOWN_LIMITATIONS.md

## What this doesn't do
Cashless denials, settlement delays, factual disputes about treatment,
whether the hospital's rates were fair

## Running locally
uv sync, ollama pull, ingest, run the API, run the frontend

## Running with Docker
## Deploying to Kubernetes
```

No mention of AI assistance anywhere in this file.

---

# PART 10 — GOTCHAS ALREADY PAID FOR

These have all bitten this project once. Do not reintroduce them.

| # | Trap | Symptom | Fix |
|---|---|---|---|
| 1 | `num_ctx` defaults to 2048 | Nonsense verdicts, no error raised | `num_ctx=8192` |
| 2 | LLM doing arithmetic | Wrong totals, inconsistent between runs | Model returns limits only |
| 3 | No caching | Hours per eval run | Hash-keyed disk cache |
| 4 | Mixing embedding models | Search returns garbage | One model; rebuild the index if it changes |
| 5 | `extract_text()` on a table | Rows collapse; the model reads the wrong row and is confident | `extract_tables()`, forward-fill merged cells |
| 6 | Scoring a real source as fabricated | A correct citation counted as an invention | `citable_ids()` loads every checkable source; it has its own test |
| 7 | Blocking HTTP for 60s | Frontend appears frozen | Background job + polling |
| 8 | Baking the **LLM** into a Docker image | 6 GB image, slow rebuilds | Mount as a volume. This does **not** apply to the 1.6 GB embedding weights — see PART 14 |
| 9 | Committing `data/db/` | Repo bloats to gigabytes | Gitignore it |
| 10 | Secrets in the repo | Fails any review | `.env` gitignored, `.env.example` committed |
| 11 | Building the frontend before the API is verified | Debugging two layers at once | Phase 8 must pass first |
| 12 | Fixing the table code without reading the output | Three regressions happened this way | Golden-file test; read the extracted text by eye |

---

# PART 11 — DO NOT

- Do not run any git command
- Do not add `Co-Authored-By`, "Generated with", a robot emoji, or any AI
  attribution anywhere
- Do not mention Claude, AI or an assistant in code, commits, PRs or docs
- Do not let the LLM compute any final amount
- Do not edit `eval/answer_key.json` to match the system's output
- Do not loosen a metric or threshold to make a number pass
- Do not delete a recorded row from `eval/results.md`
- Do not touch `data/policies/` — those are the source documents
- Do not add authentication, user accounts, or a database
- Do not add Redis, Celery, SQLite, Ragas or Langfuse
- Do not build the frontend before Phase 8 is verified
- Do not stall the whole build waiting for me; record and continue

---

# PART 12 — DEFINITION OF DONE

- [ ] `eval/results.md` has every row, v0 to v5, with any withdrawn rows marked
- [ ] Fabricated clause count is 0, and the metric has its own test
- [ ] All PyUnit tests pass
- [ ] Selenium 4 E2E test passes
- [ ] `docker-compose up` starts all six services
- [ ] `kubectl apply -f k8s/` deploys on minikube
- [ ] `Jenkinsfile` present and `JENKINS_SETUP.md` followable by a beginner
- [ ] Annotated tags v0-v5 and v1.0.0 in `GIT_COMMANDS.md`
- [ ] The git history shows GitFlow branches, a squash, a rebase, a cherry-pick,
      a revert, and the tags
- [ ] Every commit message carries a `[BA-XX]` ticket
- [ ] No AI attribution anywhere in the repo
- [ ] README leads with the results table
- [ ] README has "Where it still fails" and "What this doesn't do"
- [ ] `PROGRESS.md`, `DECISIONS.md`, `GIT_COMMANDS.md` are current
- [ ] `GIT_COMMANDS.md` runs top to bottom as one script, with checkpoints
      between phases and a comment above every block
- [ ] No `git add .` anywhere in it — every block adds only its own files
- [ ] `BLOCKED.md` lists everything that needs me, or says there is nothing

---

# PART 13 — IF YOUR CONTEXT WAS LOST

Read, in this order: `CLAUDE.md` (Current state), this file, `PROGRESS.md`
(what has been done), `DECISIONS.md` (choices already made — do not relitigate
them), `BLOCKED.md` (what needs me), `eval/results.md` (the scores),
`KNOWN_LIMITATIONS.md` (known-broken things that are not yours to fix).

Then say what you found, what phase you believe is next, and carry on. Do not
start over. Do not re-run phases already recorded in `PROGRESS.md`.

---

# PART 14 — DECISIONS TAKEN AFTER PHASE 11

Every phase in this file is built. What follows was decided afterwards, from
measurements rather than from the plan, and is recorded here so it is not
relitigated. Full write-ups in `DECISIONS.md` as D-12 and D-13.

## The per-line worker pool (D-12)

Lines were judged one at a time. On Groq a line is 6.1s and almost all of it
is a socket wait, so a ten-line bill spent a minute doing nothing four times
over. `core.audit._judge_every_line` now runs them through a
`ThreadPoolExecutor`, `BA_AUDIT_WORKERS` deciding how many.

**The default is 2, and it is measured.** B01 through the gateway on Groq,
cache off, idle machine:

| workers | wall clock | per line | speed-up | model | limiter asleep |
|---|---|---|---|---|---|
| 1 | 222.6s | 22.3s | 1.00x | 14.1s | 0.0s |
| 2 | **175.1s** | 17.5s | **1.27x** | 16.7s | 0.0s |
| 4 | 170.6s | 17.1s | 1.30x | 14.6s | 37.3s |

The plan assumed 4 on Groq, on the theory that its 30-requests-a-minute free
tier was the binding constraint. It is not. The second worker is worth 1.27x
and the third and fourth are worth 2.6% — noise — while putting the token
bucket to sleep for 37 seconds.

**The pool is a small win because the model was never the cost.** It is 6-8%
of the wall clock at every width. The rest is retrieval, and a single search
already pegs all ten cores, so more workers queue for something that was never
idle. Concurrency cannot speed up a saturated resource. Making this materially
faster means making the reranker cheaper, not running more of it at once.

**It also found a bug that sequential execution could never reach.**
`lru_cache` is not atomic: on the first audit all four workers missed the same
cold cache and each opened its own Chroma client on one directory, which is a
500 from `/search`, not a slow path. `core/retrieve.py` locks the lazy builders
and warm-up now builds the vector store and the per-policy retrievers too.

Two properties are pinned by `tests/test_workers.py` because losing either is
silent:

- Results are placed by index, never appended as they land. Rows that reshuffle
  between runs make the eval flaky and a diff of two audits unreadable.
- Progress counts completions, not dispatches. Counting dispatches shows
  "checked 10 of 10" a second in and then stalls.

**The second pass is not parallel and must not become so.** It reads every
line's verdict; that is the entire point of it. Only the first pass is
independent.

## The embedding weights are baked into the image (D-13)

PART 10 gotcha 8 says not to bake a model into an image. That is about the
5 GB LLM, and it still holds — Ollama's weights are a mounted volume.

It does not hold for bge-base and bge-reranker. A container without them
downloads 1.6 GB on first boot, which was measured at **606s** and forced a
15-minute readiness window. That is not a slow start, it is a dependency: the
pod cannot serve traffic without HuggingFace being up, and on a box with no
internet — which is what the Oracle deployment is — it never starts at all.

So they are fetched in the builder stage and `HF_HUB_OFFLINE=1` is set in the
final image, which turns a missing file into a failed build here instead of a
failed pod there.

Measured after the change: **`docker compose up -d` to `/ready` returning 200
is 13.8s**, of which 10.5s is the load. It was 606s. The readiness window drops
from 15 minutes to 3, and the cost is 1.5 GB in retrieval-service and 419 MB in
ingestion-service.

## Retrieval caching, and the rerank candidates that stayed at 20 (D-14, D-15)

Retrieval is ~92% of an audit. Two things were tried against it.

**Kept: a (query, policy) cache** in front of the retrieve-subchunk-rerank
stack, bounded at 512 and dropped whenever `clauses.json` changes. B01 through
the gateway, with every LLM call already cached so the model made **zero**
calls in both runs:

| retrieval cache | model calls | wall clock |
|---|---|---|
| cold | 0 | 207.0s |
| warm | 0 | **0.3s** |

The 207 seconds were retrieval and nothing else. But an identical bill re-run
is the best case; across different bills the overlap is partial, and the six
retried lines rewrite their queries into fresh keys. This is a demo-replay
figure, not a typical one.

**Reverted: halving the rerank candidates** from 20+20 to 10+10. Line accuracy
68.3% -> 67.1% - one line in 82, with citation accuracy moving the other way.
Possibly noise; reverted anyway, because a latency win is not a reason to
accept a worse accuracy number. `eval/results.md` records the run.

**Found while doing it:** parallel judging aborts the process on a Mac, where
the models sit on MPS and share one Metal command queue. SIGSEGV, then SIGABRT
once the load race was fixed and the crash moved to inference. Serialised
behind one lock, which the 1.27x measurement says costs nearly nothing.
