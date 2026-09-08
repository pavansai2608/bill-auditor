# CLAUDE.md

Operating rules for working in this repository. The engineering record - why the
splitter, the retrieval, the guardrails and the pipeline are built the way they
are - is `ENGINEERING.md`. The phase plan is `PHASES.md`.

## Current state (update this at the end of every phase)

**Last updated: 2026-09-06. Every phase in `PHASES.md` is built, including
Jenkins. The recorded eval is `v11` at 55.2% line accuracy over all 44 bills.
The CI gate runs the 10-bill subset against a 56.1% baseline at
`--threshold 0.52`. 492 tests.**

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
  anything the cluster is live on. The Eval and E2E stages need a model server
  on `localhost:11434`, which `ci/com.ollama.serve.plist` keeps running as a
  LaunchAgent — the native Ollama, never the container, which publishes no host
  port on purpose. Without it both gates go NOT_BUILT and the build is UNSTABLE
  for a reason that has nothing to do with the commit; see `JENKINS_SETUP.md`
  section 11.
- `.github/workflows/pages.yml` — the front end alone on GitHub Pages at
  <https://pavansai2608.github.io/bill-auditor/>, on push to `main`. **Separate
  from Jenkins and does not touch it.** `npm run build:pages` reads
  `frontend/.env.pages`: base `/bill-auditor/`, `index.html` copied to
  `404.html`, and `VITE_STATIC_DEMO` disabling the submit path — there is no
  API on a CDN, so the form explains itself and points at the quickstart
  instead of posting into nothing. The report screen is fed
  `frontend/src/data/exampleReport.json`, exported from the v11 B01 checkpoint
  by `eval/export_example_report.py`; it is a real run, and
  `tests/test_example_report.py` pins its citations to `data/clauses.json`,
  because a fabricated citation in a committed file is not covered by the
  metric that keeps fabrications at zero everywhere else.
  `tests/e2e/pages_static_check.py` serves `dist/` the way Pages does — the
  subpath, and `404.html` under a real 404 status — and checks it in a browser,
  because every one of these fails **only** in production and looks perfect
  against a dev server at the domain root. **No secret belongs in that
  workflow, in `.env.pages`, or in the bundle:** a `VITE_` variable is not
  configuration, it is a string anyone can fetch off the published site.
- The clause index: 399 clauses in `data/clauses.json` (star_health 152,
  hdfc_ergo 143, niva_bupa 104) plus `non_payable.json`. Counted out of the
  file on 2026-09-06; `PROJECT_FACTS.md` records the same figure and the
  flattened-table fix that took it down from 402.
- The eval harness: **44 bills** in `eval/bills/`, an answer key derived
  straight from the PDFs by `eval/derive_key.py`, and `eval/evaluate.py`
  (`--agent` scores the loop, without it scores naive v0).
  `eval/make_text_bills.py` writes each bill out as pasteable text under
  `eval/bills/text/` with an `INDEX.md` of the form inputs, and checks the
  `bill_text` and the `lines` array of every bill against each other — the two
  halves of a fixture can drift and nothing else compares them. `--llm` runs
  the same check through `core.bill.parse_bill` instead of the regex.
- 492 PyUnit tests, all passing, `unittest discover -s tests` in ~75s.

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

## Definition of done

This applies to every change, without being restated. A change is not done when
the edit is made; it is done when the pipeline that guards this repository has
been run against it and has come back green.

**1. Run what Jenkins runs, before handing over any git command.** Not an
approximation of it - read the `Jenkinsfile` and run the commands it actually
contains. Today the Build, Lint, Unit and Quality stages are:

```bash
uv sync --frozen --all-extras      # Build
uv run pyb clean                   # Build
uv run ruff check .                # Quality / Lint
uv run ruff format --check .       # Quality / Lint
uv run pyb --no-venvs run_unit_tests   # Quality / Unit
```

**Any change under `frontend/` additionally has to pass the Pages build**,
because Jenkins does not build it and will happily stay green while the
published site breaks:

```bash
cd frontend && npm ci && npm run build:pages
```

That must exit 0 before anything is handed over. It is not the same as
`npm run typecheck`: the failure that took main's Pages build down had a clean
typecheck and a clean build, and died on the workflow's own guard step.

If a stage in the `Jenkinsfile` changes, this list is stale and the
`Jenkinsfile` wins. Re-read it rather than trusting these five lines.

If `uv run pyb` answers `Failed to spawn: pyb` while `.venv/bin/pyb` plainly
exists, the console scripts carry an absolute shebang from wherever this
checkout used to live, and the directory has moved since. `rm -rf .venv && uv
sync --frozen --all-extras` rewrites them. Jenkins never sees this - it builds
its own `.venv` in the workspace - so it is a local failure only, and not a
reason to touch the `Jenkinsfile`.

**2. After the repo owner says a build has run, poll for the result.** Do not
ask for a pasted log:

```bash
curl -s "http://localhost:8080/job/bill-audit/job/develop/lastBuild/api/json?tree=number,building,result"
```

Poll until `"building": false`, then read `"result"`.

**3. Anything other than `SUCCESS` is a failure to be fixed, not reported and
left.** `UNSTABLE` counts as a failure - it is the colour a skipped gate
produces, and a gate that did not run has proved nothing. Fetch the log,
find the cause, fix it, and say what it was:

```bash
curl -s "http://localhost:8080/job/bill-audit/job/develop/<N>/consoleText"
```

**3a. GitHub Actions is a second pipeline, and it fails on its own.** Jenkins
knows nothing about `.github/workflows/pages.yml`, so a green `develop` proves
nothing about the published site. After a push to `main`, poll the Pages
workflow the same way and to the same standard. With the GitHub CLI, if it is
installed:

```bash
gh run list --workflow=pages --limit 3
gh run view <run-id> --log-failed
```

`gh` is **not** installed on this machine. The REST API answers unauthenticated
for this repository, which is public, and is what to reach for instead:

```bash
curl -s "https://api.github.com/repos/pavansai2608/bill-auditor/actions/runs?per_page=3"
curl -s "https://api.github.com/repos/pavansai2608/bill-auditor/actions/runs/<run-id>/jobs"
```

The `jobs` response names the failing **step**, which is the thing worth
knowing - the run's annotations are often just `Process completed with exit
code 1`, which says nothing. If `build` fails, `deploy` is skipped and the site
keeps serving the previous bundle, so a failure here is silent from the
outside: no error page, just stale content. Fetch the log, fix it, and say what
it was, without waiting to be asked.

**4. Never buy a green build by weakening what it measures.** Not by lowering a
threshold, not by editing an evaluation file or an answer key, not by deleting
or rewriting a recorded result, not by widening a `when` so a stage skips
quietly, not by turning an error into a warning, and not by reverting a real
fix to recover a number. A stage that genuinely cannot run on this agent should
say so loudly and leave the build yellow. If the only route to green runs
through weakening a check, stop and say so instead - that finding is the
deliverable.

**5. Never run a git command**, per the working rules below. Hand the commands
over as text.

**6. No AI attribution anywhere** - not in commits, code, comments or docs. Also
per the working rules below.

### Authenticating to the Jenkins API

**Nothing is needed for reading.** This instance allows anonymous read: plain
`curl` against `/api/json` and `/consoleText` returns 200, and
`http://localhost:8080/whoAmI/api/json` reports `"name": "anonymous"` with
`"authenticated": true`. Every command in this section works as written.

If read access is ever locked down, or something needs to be *triggered* rather
than read, it takes an API token - a real one, not the account password, which
Jenkins rejects for API use:

1. Jenkins → your name, top right → **Security** (or go straight to
   `http://localhost:8080/user/<your-user>/security/`).
2. **API Token** → **Add new Token** → name it → **Generate**.
3. Copy it then and there. Jenkins shows it once and never again.

Keep it out of this repository. Put it in a shell variable or `~/.netrc`, and
pass it as `curl -u "<user>:$JENKINS_TOKEN"`. A POST additionally needs a CSRF
crumb:

```bash
CRUMB=$(curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  'http://localhost:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)')
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" -H "$CRUMB" -X POST \
  "http://localhost:8080/job/bill-audit/job/develop/build"
```

A token in a commit is a token to revoke, at Jenkins → your name → Security →
the token's **Revoke** button.

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
docker compose up -d                           # all six services; UI on :5173, gateway on :8000
uv run uvicorn api.main:app --reload           # the api/ monolith instead; eval and E2E use this
uv run python eval/evaluate.py                 # full 44-bill eval, naive v0 path
uv run python eval/evaluate.py --agent --version v2 --write   # score the agent loop, append to results.md
uv run python eval/evaluate.py --quick --threshold 0.80   # CI gate; exit 1 below threshold
uv add <pkg>                              # then: uv export --format requirements-txt --no-hashes > requirements.txt
```

Tests are **PyUnit (`unittest`)**, not pytest — Jenkins drives them through PyBuilder (`pyb run_unit_tests`). `requirements.txt` is a generated export, never hand-edited.

Groq answers the model calls for the API and the UI (`BA_GROQ_API_KEY` in `.env`), with Ollama as the per-call fallback when Groq refuses one. The eval, the CLI and the tests default to Ollama, so it must be running with `qwen3:8b` pulled for any of those.

## Git workflow

GitFlow: `main` (tagged releases only) ← `release/vX` ← `develop` ← `feature/short-name`. Commits are Conventional Commits: `feat(agent): add retry loop with query rewriting`. The `.githooks/commit-msg` hook enforces the format and a 72-character subject limit; `.githooks/pre-commit` runs ruff. Install with `git config core.hooksPath .githooks`.

**Every commit carries a `[BA-XX]` ticket**, at the end of the subject, enforced by `.githooks/commit-msg` — install it with `git config core.hooksPath .githooks` or it does nothing. Numbering is continuous across the whole history; find the next free number with `git log --all --format=%s | grep -o '\[BA-[0-9]*\]'`. See D-01.

**Always branch from `develop`.** Running `git checkout -b feature/next` while still standing on the previous feature branch stacks them, and `develop` then holds none of the work — which has already happened once here. `git checkout develop` first, every time.

Annotated tags mark eval milestones: `v0` naive baseline · `v1` hybrid retrieval · `v2` agent loop · `v3` second pass · `v4` all 8 guardrails · `v1.0.0` submission.

When eval accuracy drops between tags, `git bisect run python eval/evaluate.py --quick --threshold 0.80` finds the commit — surface this whenever a drop is recorded in `results.md`.

## Do not add

SQLite, Redis, Celery, Ragas, Langfuse, any paid API, authentication, or a database. LangChain text splitters on policy documents.
