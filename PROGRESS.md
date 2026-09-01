# Progress

One entry per phase, in order. The four blocks the spec asks for. Phases 1-7
predate this file and are summarised; Phase 8 onward is written in full.

---

# Phases 1-7 and the two accuracy passes (summary)

| Phase | What landed | Eval |
|---|---|---|
| 1 | `core/config.py`, `llm.py` (Ollama plus a disk cache), `logging_conf.py`, `models.py` | — |
| 2 | The splitter and ingestion: PDFs to 402 numbered clauses, tables read structurally, frozen by golden files | — |
| 3 | Hybrid retrieval: Chroma plus BM25 at 0.6/0.4, sentence windows, cross-encoder rerank | — |
| 4 | `core/audit.py`, the naive baseline | v0 24.4% |
| 5 | 44 bills and an answer key derived from the PDFs, not from the pipeline | — |
| 6 | `core/agent.py`, the LangGraph retry loop | v2 51.2% |
| 7 | `core/second_pass.py`, proportionate deduction | v3 54.9% |
| — | `core/room_limit.py`, the room limit read from the table | v4 59.8% |
| — | `core/waiting.py`, waiting periods from dates | v5 68.3% |

Fabricated citations: 0 at every version.

Two eval rows were withdrawn and re-run rather than deleted, with the reasons
recorded in `eval/results.md`: the first v2 counted 18 correct `IRDAI-List-I`
citations as fabrications (a scorer bug, now covered by
`tests/test_eval_scoring.py`), and the first v3 took its proportionate ratio
from any breached per-day cap including an ICU line (a second-pass bug, now
covered by `OnlyRoomRentDrivesTheDeductionTest`).

---

# Phase 8 — API

## WHAT I DID

The audit now has a web API, written with FastAPI, in `api/`. An audit takes
30 to 60 seconds, which is far too long to make a browser wait, so no endpoint
does the work while the request is open. `POST /audit` checks the inputs, starts
the audit in a background worker and immediately returns a short job id. The
browser then calls `GET /audit/{job_id}` every couple of seconds and gets back
`{"status":"running","done":3,"total":10}` until the audit finishes, at which
point the same URL returns the finished report.

The progress numbers are real. `audit_lines` in `core/audit.py` now takes an
`on_progress` function and calls it after each bill line is decided, so
`done`/`total` tracks lines actually judged rather than a guess.

`POST /compare` runs the same bill against all three policies using the same job
pattern, and says which policy pays most and by how much. `POST /policies/upload`
takes a user's own policy PDF, checks it really is a PDF by looking at the first
four bytes rather than trusting the filename, stores it under a name rebuilt from
scratch so an upload cannot write outside the policies folder, and re-indexes in
the background. `GET /policies` returns the dropdown, including the sums insured
each policy actually supports — star_health's nine values come from its own
clause II.1 table.

The report the API returns carries the line-by-line verdicts, the totals, the
full trace, and an `assumptions` block lifted out of the trace so a user can see
that differential billing was assumed rather than proven.

Two safety details. The bill text is masked for patient identifiers at the edge,
before the job stores anything, because a job outlives the request. And a failure
inside the background work sets the job to `failed` with a readable message
instead of leaving it stuck on `running` forever.

`core/` still imports no web framework.

## FILES CHANGED

- created `api/main.py`
- created `api/jobs.py`
- created `tests/test_api.py`
- created `PHASES.md`, `PROGRESS.md`, `DECISIONS.md`, `BLOCKED.md`, `GIT_COMMANDS.md`
- modified `core/audit.py` (the `on_progress` callback)
- modified `core/config.py` (CORS origins, upload cap, 100-job cap)
- modified `core/room_limit.py` (`sum_insured_options`)
- modified `CLAUDE.md` (Current state, layout, the uvicorn command)
- modified `pyproject.toml`, `uv.lock`, `requirements.txt` (fastapi, uvicorn, python-multipart)

## GIT COMMANDS

In `GIT_COMMANDS.md` under "Phase 8".

## VERIFY IT WORKED

```bash
uv run python -m unittest tests.test_api
```

Expect `Ran 29 tests ... OK`.

`AuditTest.test_polling_returns_the_report_with_its_trace_and_assumptions`
failing means the report reached the browser without its trace or its
assumptions. The rupee figures would still look correct, which is exactly why
it is asserted: a deduction the user cannot trace back to a clause is the thing
this project exists to replace.

`AuditTest.test_a_job_is_polled_from_running_to_done` failing means the
progress counter is not moving, so the frontend would show a frozen 0/0 for a
minute and look broken.

`AuditTest.test_the_bill_is_masked_before_it_reaches_the_job` failing means a
patient name can now sit in the job store for the life of the process.

Live check:

```bash
uv run uvicorn api.main:app --reload
```

Open http://localhost:8000/docs — Swagger UI titled "Bill Auditor" with all
eight endpoints. `curl http://localhost:8000/health` reports `"clauses":402`
and the three policies. `"status":"degraded"` there means the clause index is
missing and `uv run python -m core.ingest` needs to run first.

---

# Phase 9 — Frontend

## WHAT I DID

The audit now has a browser interface, built with React, TypeScript and Vite,
with React Query doing the polling.

The design was written down before any component: `frontend/design/tokens.json`
holds every colour, text size and spacing step, and `frontend/design/README.md`
holds the screen and state specs. `src/styles.css` mirrors those token names as
CSS variables, so nothing in the interface is a number somebody guessed. Stitch
itself was not reachable from this workspace, which is recorded as B-05 in
`BLOCKED.md`.

Screen 1 takes the bill either as a dropped file or pasted text — a toggle, so
it is never unclear which one will be sent — then the insurer, the sum insured,
the two dates, and the optional room limit. The sum-insured list comes from the
API for the chosen insurer, because Star Health prices its room limit by sum
insured and the other two do not. The room-limit field carries its helper text
permanently: leaving it blank is fine and the audit will say so rather than
assume a figure.

Screen 2 leads with the money. Charged, deducted, payable and flagged sit in a
band across the top, and the deducted figure is set at three times the body size
in a deep red, because that is the number the patient came for. Below it the
assumptions panel is always on screen, never behind a toggle. Then the table:
item, charged, allowed, the clause chip, and the reason. Every row opens to show
the trace of how that line was decided. Flagged rows are amber rather than red —
a flagged line is the system refusing to guess, not an error.

The parts the syllabus asks for are all real rather than decorative. The
`useAuditJob` hook owns the whole polling loop: start the job, poll every two
seconds, stop the moment the status is `done` or `failed`, and give up after
five minutes with a message naming Ollama as the likely cause. Context carries
the form values and the running job. There is an error boundary around the form
and another around the report, so a crash in one cannot blank the other. The
report and compare screens are loaded with `React.lazy`, which the build
confirms: they come out as separate 4.6 kB and 1.2 kB chunks rather than sitting
in the main bundle.

On a phone the table stops being a table and becomes one card per line, with
each cell labelled by its column name.

## FILES CHANGED

- created `frontend/package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `.env.example`, `.gitignore`, `README.md`
- created `frontend/design/tokens.json`, `frontend/design/README.md`
- created `frontend/design/screenshots/` (four PNGs, both screens at 1440px and 390px)
- created `frontend/src/main.tsx`, `App.tsx`, `styles.css`, `types.ts`
- created `frontend/src/lib/api.ts`, `frontend/src/lib/csv.ts`
- created `frontend/src/hooks/useAuditJob.ts`
- created `frontend/src/context/AuditContext.tsx`
- created `frontend/src/components/` — `BillForm.tsx`, `ReportView.tsx`, `CompareView.tsx`, `LineRow.tsx`, `AssumptionsPanel.tsx`, `RunningPanel.tsx`, `Skeletons.tsx`, `ErrorBoundary.tsx`
- created `tests/e2e/__init__.py`, `tests/e2e/test_flow.py`, `tests/e2e/capture_screenshots.py`, `tests/e2e/README.md`
- modified `BLOCKED.md` (B-05, Stitch not connected)

## GIT COMMANDS

In `GIT_COMMANDS.md` under "Phase 9".

## VERIFY IT WORKED

With the API and the frontend both running:

```bash
uv run python -m unittest tests.e2e.test_flow
```

Expect `Ran 2 tests ... OK` in about 40 seconds.

`AuditFlowTest.test_a_pasted_bill_produces_a_cited_report` asserts the payable
figure is exactly Rs 25,000. That number is not arbitrary: the room line
resolves from the Star Health table at 5,000 a day for five days, and the gloves
are item 56 on the IRDAI non-payable list. If it fails, either the room table
stopped being read correctly or the non-payable fast path stopped firing —
both far more serious than a browser problem.

The same test also checks that the deducted figure renders taller than the
charged figure, and that the assumptions panel sits above the table. Those
failing means the design intent has been lost: the report would still be
correct but would no longer lead with what the patient came to find out.

If the test skips, it prints the command to start whichever half is missing.
`BA_E2E_STRICT=1` turns those skips into failures, which is what Jenkins uses.

Build check on its own:

```bash
cd frontend && npm install && npm run build
```

Expect `ReportView-*.js` and `CompareView-*.js` as separate chunks in the
output. If they are missing, code splitting has been lost and the first page
load is carrying the whole report screen for nothing.

---

# Phase 10 — Microservices

## WHAT I DID

The monolith was split into four Python services, which together with Ollama and
the frontend make the six containers.

- **retrieval-service** owns the search. It holds the Chroma collection, the
  BM25 index and the reranker, and answers `POST /search` in milliseconds. It
  never calls the model and never decides anything.
- **audit-service** owns the agent loop, the second pass and the guardrails. It
  does not do its own searching: on startup it points `core.agent.search` at
  retrieval-service over HTTP. That is a one-line swap because the agent imports
  `search` by name, and it means the audit rules themselves are untouched.
- **ingestion-service** owns the PDFs, the splitting and the embeddings. It is
  the only image that carries `data/policies/`.
- **gateway** is the only service the browser talks to. It parses the form,
  masks the bill before it crosses a network boundary, and forwards.

Nothing was copied. Every service imports the same `core/`, and the request
handling the gateway and the monolith share was lifted into `api/shared.py`
rather than written twice. The monolith in `api/` still works and is what the
eval and local development use — that choice is D-10 in `DECISIONS.md`.

The gateway's `/health` asks each dependency for its own health and reports
`degraded` if any of them is down, so one call says what is broken.

## FILES CHANGED

- created `services/common.py`, `services/__init__.py`
- created `services/retrieval/main.py`
- created `services/audit/main.py`, `services/audit/remote_retrieval.py`
- created `services/ingestion/main.py`
- created `services/gateway/main.py`
- created `api/shared.py` (lifted out of `api/main.py`)
- created `tests/test_services.py`
- modified `api/main.py` (imports the shared helpers instead of holding them)
- modified `core/config.py` (service URLs and the service timeout)
- modified `pyproject.toml`, `uv.lock`, `requirements.txt` (httpx is now a runtime dependency)

## GIT COMMANDS

In `GIT_COMMANDS.md` under "Phase 10".

## VERIFY IT WORKED

```bash
uv run python -m unittest tests.test_services
```

Expect `Ran 17 tests ... OK`.

`RemoteRetrievalTest.test_installing_patches_both_call_sites` failing is the
serious one: `core.audit` imports `search` into its own namespace as well as
`core.agent`, so patching only one would leave half the system trying to open a
Chroma collection the container does not have.

`GatewayTest.test_an_audit_is_forwarded_with_the_bill_already_masked` failing
means a patient's name would travel between containers.

`GatewayTest.test_a_dead_inner_service_is_a_502_not_a_stack_trace` failing means
a container being down would surface as a 500 with a traceback rather than a
readable message naming the service that did not answer.

---

# Phase 11 — DevOps

## WHAT I DID

The project can now be built, tested, containerised and deployed by commands
someone else can run.

**Docker.** A Dockerfile per service, all multi-stage: dependencies are built
once and copied into a slim runtime. The frontend is built with Node and served
by nginx, so the published image has no Node in it. `docker-compose.yml` wires
all six together, publishes only the gateway and the frontend, and gives every
service a healthcheck so `docker compose ps` tells the truth. The Ollama model
is a named volume — baking 5 GB into an image would mean re-downloading it on
every rebuild.

**Kubernetes.** `k8s/` holds a Deployment and a Service per component, a
ConfigMap for the settings, a Secret template, three PersistentVolumeClaims (the
model, the clause index, the model-call cache), and liveness and readiness
probes on `/health` everywhere. Resource limits match how the services actually
behave: audit-service gets the most, retrieval runs two replicas, ingestion gets
memory but no traffic. `BA_OLLAMA_BASE_URL` in the ConfigMap is the only thing
that decides where the judge model lives, so a cluster can point at a hosted
model and scale Ollama to zero. Every manifest was checked with
`kubectl apply --dry-run=client`.

**PyBuilder.** `build.py` runs the PyUnit tests, flake8 and coverage. Coverage
measured 79%, so the gate is set at 75 — a threshold the build can meet today
rather than one that fails on day one.

**Jenkins.** The `Jenkinsfile` is a multibranch pipeline: `feature/*` runs Build
and Quality, `develop` adds Eval and E2E, `main` adds Docker and Deploy. The
Eval stage runs the auditor against the answer key and fails the build below
0.65 line accuracy — unit tests can pass while the audit gets quietly worse, and
that stage is what makes it visible. `JENKINS_SETUP.md` walks through installing
Jenkins, the plugins, credentials and the job, and has a section on what to do
when the Eval stage goes red (the answer is never "raise the threshold").

**README.** Rewritten to lead with the results table and both screenshots, with
a worked example in rupees, the architecture and why it is split that way, what
was learned, where it still fails, and what the project deliberately does not
do.

## FILES CHANGED

- created `services/*/Dockerfile` (four), `frontend/Dockerfile`, `frontend/nginx.conf`
- created `docker-compose.yml`, `.dockerignore`
- created `k8s/` — namespace, config, storage, six deployments and services, `README.md`
- created `build.py`, `.flake8`
- created `Jenkinsfile`, `JENKINS_SETUP.md`
- modified `README.md` (rewritten)
- modified `.gitignore` (`.pybuilder/`, `target/`, coverage output)
- modified `pyproject.toml`, `uv.lock`, `requirements.txt` (coverage and flake8 as dev dependencies)

## GIT COMMANDS

In `GIT_COMMANDS.md` under "Phase 11".

## VERIFY IT WORKED

```bash
uv run pyb clean analyze run_unit_tests
```

Expect `BUILD SUCCESSFUL` and `Executed 231 unit tests`. A flake8 failure here
that ruff does not report means the two configs have drifted apart — fix
`.flake8`, not the code.

```bash
docker compose config >/dev/null && echo compose ok
kubectl apply --dry-run=client -f k8s/
```

The first prints `compose ok`; the second lists fifteen objects with
`(dry run)` after each. A failure in the second is a manifest problem, not a
cluster problem — it does not need a cluster to pass.

Nothing here was run against a real cluster or a Jenkins server: B-01, B-02 and
B-03 in `BLOCKED.md` say exactly what to run to confirm them.
