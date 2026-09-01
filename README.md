# Bill Auditor

Audits an Indian health insurance claim bill against the policy that governs it,
line by line, and names the clause behind every deduction.

![The audit report](frontend/design/screenshots/screen-2-audit-report-1440.png)

## Results

Measured against 44 hand-written bills whose answers were derived from the
policy PDFs directly, never from this system. Line accuracy means the rupee
figure matches the key within Rs 1.

| Version | What changed | Line accuracy | Citation accuracy | Fabricated citations |
|---|---|---|---|---|
| v0 | Naive: one search, one judge call, no retry | 24.4% | 22.2% | **0** |
| v2 | LangGraph agent loop, retried on low confidence | 51.2% | 33.3% | **0** |
| v3 | Proportionate-deduction second pass | 54.9% | 44.4% | **0** |
| v4 | Room limit read from the table, not the model | 59.8% | 48.1% | **0** |
| v5 | Waiting periods decided from dates, not the model | **68.3%** | **56.8%** | **0** |

A fabricated citation — a clause id that does not exist in the policy — is the
worst thing this system could produce, because it is confident and
unverifiable. It has been 0 at every version, and the way it is counted has its
own test.

Full tables, including two rows that were withdrawn and re-run with the reason
recorded, are in [`eval/results.md`](eval/results.md).

## The problem

An insurer pays part of a hospital bill and sends a letter saying "deducted as
per policy terms". The patient has no way to check that. The rules are real,
but they are spread across a 50-page PDF written for lawyers.

Here is a real bill this system audited, on a Star Health policy with a
Rs 3,00,000 sum insured:

| Item | Charged | Payable | Because |
|---|---|---|---|
| Room rent (single A/C), 8,000 x 5 days | 40,000 | 25,000 | II.1 caps the room at 5,000 a day at this sum insured |
| ICU charges | 60,000 | 10,000 | judged against the same clause |
| Surgeon fee | 80,000 | 9,375 | reduced in proportion, because the room breached its cap |
| Anaesthetist charges | 15,000 | 9,375 | same proportionate deduction |
| Medicines and drugs | 38,000 | 38,000 | II.16 |
| Surgical gloves | 1,200 | 0 | item 56 on the IRDAI non-payable list |
| Disposable syringes | 1,500 | **flagged** | no clause clearly covered it, so it was not guessed at |
| Ambulance charges | 2,500 | 750 | II.8 caps road ambulance at 750 |

**Rs 2,40,000 charged, Rs 94,000 payable, one line flagged for a human.**

The surgeon's fee is the interesting one. Nothing in that line mentions the
room. It was reduced because the *room* breached its cap, and the policy shrinks
the associated medical expenses in the same proportion. No line-by-line check
can ever find that.

Two things it gets wrong, in its own words: a cataract bill with no sub-limit
comes back flagged rather than paid in full, and a Star Health bill inside the
24-month waiting period is not excluded because that policy's list of conditions
did not survive PDF extraction. Both are in
[`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

## How it works

![The input screen](frontend/design/screenshots/screen-1-audit-a-bill-1440.png)

Setup runs once, offline: the policy PDFs are split on their clause numbers into
402 numbered clauses, embedded into ChromaDB, and indexed for BM25. Tables are
read structurally rather than as flowing text, because `extract_text()` reads a
room-rent table straight across and puts the wrong limit next to the wrong sum
insured.

Then, per bill line:

1. **Non-payable fast path.** Gloves, syringes and the rest of the IRDAI list
   are settled with no search and no model call. About a third of real bill
   lines are consumables.
2. **Room rent is a lookup.** Policy plus sum insured names the table row. The
   model is not asked, because it once read 800 a day off a table that grants a
   room category.
3. **Waiting periods are a date subtraction.** Two dates and the number the
   clause states.
4. **Everything else goes to the loop:** classify the rule type, build a query,
   hybrid retrieve (Chroma and BM25 fused 0.6/0.4), rerank to the top 3, then
   ask the model one narrow question — which clause applies and what limit does
   it state.
5. **Python does the arithmetic.** Always.
6. **The second pass.** Once every line has a verdict, a breached room-rent cap
   rescales the associated medical expenses. This is the part no per-line audit
   can do.

## How it decides when to stop

- **Three attempts, eight tool calls.** Then it abstains.
- **A confident answer is never re-asked.** Re-asking is where latency goes for
  no accuracy.
- **Two identical retrievals in a row stop the loop.** A third would cost a
  model call and tell us nothing.
- **A citation that is not in the index is rejected outright**, and the line
  abstains rather than retrying — the model was confident, so asking again gets
  the same answer.
- **Below the rerank threshold the model is not called at all.** Reasoning over
  clauses that do not apply is worse than admitting the search missed.
- **When it abstains it says why**, and the line goes to a human.

The LLM never computes an amount. `JudgeOutput` deliberately has no `allowed`
field: the model reports a limit and a clause id, and Python multiplies. An 8B
model asked to multiply 5,000 by 5 will sometimes answer 20,000 and sound
certain, and a wrong total is invisible in a way a wrong citation is not.

## Known assumptions

Both Star Health and HDFC Ergo disapply proportionate deduction at hospitals
that "do not follow differential billing". Nothing on a hospital bill says
whether that hospital does, and no input to this system could carry it.

So the assumption is made — the deduction applies — and it is **printed with
every report**, stored in the trace with the clause that creates the problem,
and shown on screen in a panel that is never behind a toggle. `--no-differential-billing`
turns it off.

The other one is the room limit. Two of the three policies state no figure at
all: HDFC says "At Actuals unless otherwise specified in the Policy Schedule",
and Niva Bupa caps by room category "as specified in your Policy Schedule". So
there is an optional fourth input for it, and **leaving it blank is a valid
answer**: room-dependent lines come back flagged with the reason "room limit is
set by the policy schedule, which was not provided". Not a default. Not a guess.

## Evaluation

44 bills, 330 lines, across the three policies, covering clean bills, room-rent
breaches, non-payable items, sub-limits and waiting periods.

**The answer key was derived by reading the policy PDFs, not by running the
pipeline.** `eval/derive_key.py` opens the PDFs with pdfplumber and imports no
retriever, judge or audit code, so a bug in the system cannot write itself into
the key and then be scored as a success. Every answered line quotes the sentence
it came from and shows the arithmetic:

```
"II.1 p10 table: Sum Insured 300,000 -> Up to 5,000/- per day;
 5,000 x 5 = 25,000, min(40,000, 25,000) = 25,000"
```

Ten of the 44 were then checked by hand against the source PDFs; the list is in
`eval/answer_key_provenance.md`.

Every metric is deterministic — a number matches or it does not, a clause id
matches or it does not. Nothing is scored by a model. An LLM judging its own
output would only tell us the system agrees with itself.

Category accuracy at v5:

| Category | Lines | Accuracy |
|---|---|---|
| non_payable | 29 | 79.3% |
| clean | 15 | 73.3% |
| waiting_period | 7 | 100% |
| room_rent_over | 25 | 60.0% |
| sub_limit | 6 | 0.0% |

## Architecture

Six containers. Only the gateway and the frontend are published; the three inner
services are reachable on the compose network and nowhere else.

```
browser ──> frontend (nginx)
                │
                v
            gateway ──────> audit-service ──> retrieval-service ──> Chroma + BM25
                │                 │
                │                 └────────> ollama (qwen3:8b)
                └──────────> ingestion-service ──> Chroma
```

They are split because they scale differently, which is the only honest reason
to split anything:

- **ingestion** is heavy but rare. Splitting and embedding three PDFs takes
  minutes and a lot of memory, and happens when a policy is added, not when a
  bill is audited.
- **retrieval** is light and frequent. Every line calls it; it answers in
  milliseconds and holds the indexes in memory. It is the one worth running two
  of.
- **audit** is slow and CPU-bound. One request occupies a worker for most of a
  minute. It gets the largest limits in `k8s/`.

`core/` stays a shared library that every service imports. The audit rules are
the product, and two copies of `money.py` would eventually disagree — as a wrong
rupee figure rather than an error.

## CI/CD

Jenkins multibranch. `feature/*` runs Build and Quality; `develop` adds Eval and
E2E; `main` adds Docker and Deploy.

**The Eval stage is the distinctive part.** It runs the auditor against the
answer key and fails the build when line accuracy drops below 0.65:

```
FAIL: line accuracy 0.610 is below the threshold 0.650
```

Unit tests can pass while the audit quietly gets worse — a retrieval change, a
prompt change, a splitter change. This stage is what makes that visible, and
`git bisect run` with the same command finds the commit that did it.
Step-by-step setup, including what to do when that stage goes red, is in
[`JENKINS_SETUP.md`](JENKINS_SETUP.md).

## What I learned

- **A PDF table flattened into text corrupts every rupee figure downstream, and
  nothing errors.** Star Health's room-rent table read straight across put
  `5,00,000` next to the limit belonging to the 3L and 4L rows. The output still
  looked like text, so nothing failed — it broke three times before the golden
  files caught it.
- **Both big accuracy jumps came from taking the model out of the decision, not
  from prompting it harder.** The room limit (v4) and the waiting periods (v5)
  are a table lookup and a date subtraction. Together they were worth 13 points.
- **A scoring bug made 18 correct citations look like fabrications.** The scorer
  built its list of legitimate citations from `clauses.json` alone, so the IRDAI
  non-payable list — a real, checkable source — was counted as invention. The
  metric now has its own test, because a metric that can break silently is worse
  than no metric.
- **One wrong number can cost four wrong lines.** When the judge misread a room
  limit, the second pass faithfully propagated that wrong premise to every
  associated expense. Errors in a pipeline do not stay where they start.

## Where it still fails

- **Sub-limit lines abstain when there is no sub-limit.** The loop can find a
  cap or fail to find one; it has no way to say "nothing limits this line, so
  pay it in full". Five of six lines on a cataract bill come back flagged.
- **Star Health waiting periods are not applied.** Its clause III.2 states the
  24 months and then says "f. List of specific diseases/procedures;" — and the
  list is on the next page and did not survive extraction. The system refuses to
  act on a list it cannot read.
- **Pre-existing disease is never applied.** Nothing on a bill says whether a
  condition pre-dated the policy.
- **The recorded numbers are from 10 of the 44 bills.** A full run takes about
  45 minutes.

All four are written up with diagnoses in [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

## What this doesn't do

It does not handle cashless authorisation denials, settlement delays, or
disputes about whether a treatment was medically necessary. It does not judge
whether the hospital's rates were fair — only what the policy says the insurer
owes against the rates charged. It is not legal advice, and a flagged line means
a person still has to look.

## Running locally

```bash
uv sync
ollama pull qwen3:8b                     # the judge model, running on your machine
uv run python -m core.ingest             # build the clause index, once

uv run uvicorn api.main:app --reload     # API on :8000, docs at /docs
cd frontend && npm install && npm run dev # UI on :5173
```

On the command line, without the browser:

```bash
uv run python -m core.audit data/sample_bill.txt --policy star_health --sum-insured 300000 \
  --agent --second-pass --admission-date 2026-01-10 --policy-start-date 2023-01-01
```

Tests and the evaluation:

```bash
uv run python -m unittest discover -s tests          # 233 PyUnit tests
uv run pyb run_unit_tests                            # the same, the way Jenkins runs them
uv run python eval/evaluate.py --quick --agent --second-pass
```

## Running with Docker

```bash
docker compose build
docker compose up -d
docker compose ps                       # healthchecks make this honest
docker compose exec ollama ollama pull qwen3:8b
open http://localhost:5173              # the app
curl http://localhost:8000/health       # the gateway and its dependencies
docker compose logs -f audit-service
docker compose down                     # -v also drops the volumes
```

The model is a mounted volume, never baked into an image.

## Deploying to Kubernetes

```bash
minikube start --memory=8192 --cpus=4 --disk-size=40g
eval $(minikube docker-env)             # build into the cluster's daemon
kubectl apply -f k8s/
kubectl -n bill-auditor get pods -w
open "http://$(minikube ip):30173"
```

Full commands, including how to point the cluster at a hosted model instead of
running an 8B model in a pod, are in [`k8s/README.md`](k8s/README.md).

## Layout

| Path | What is in it |
|---|---|
| `core/` | the audit rules: splitter, retrieval, agent, second pass, money, guardrails |
| `api/` | the FastAPI monolith — one process, used for local development and the eval |
| `services/` | the same code split into four containers for deployment |
| `frontend/` | React + TypeScript, with the design tokens in `frontend/design/` |
| `eval/` | 44 bills, the hand-derived answer key, and the scorer |
| `tests/` | PyUnit, including the Selenium flow in `tests/e2e/` |
| `k8s/` | manifests for minikube |

`PHASES.md` is the build plan, `PROGRESS.md` is what was done,
`DECISIONS.md` is why, and `BLOCKED.md` is what still needs a human.
