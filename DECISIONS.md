# Decisions

Choices made without being able to ask. Each says what was picked, why, and what
would have to be true for the other option to win. Do not relitigate these.

---

## D-01 — every commit carries a [BA-XX] ticket

**Choice.** Conventional Commits with a `[BA-XX]` ticket at the end of the
subject, enforced by `.githooks/commit-msg`.

**History of this decision.** The tickets were dropped once, on the grounds that
there is no issue tracker, and then reinstated: `PHASES.md` Part 4 and the
Definition of Done both require them, and the numbering is a usable sequence
even without a tracker behind it. `GIT_FIX.md` is the rewrite that put them
back across the whole history.

**Why the enforcement matters more than the choice.** They went missing from an
entire build without anything failing, for two reasons at once: `core.hooksPath`
was never set, so no hook ran; and the hook had no ticket check in it. Both are
fixed, and `tests/test_hooks.py` runs the real hook against a message with no
ticket and asserts it is rejected.

**When the other option wins.** If a tracker is ever adopted, switch to its ids
and change the pattern in the hook and its test together.

---

## D-02 — `git revert` is left out of the planned history

**Choice.** `GIT_COMMANDS.md` contains a squash rebase, a cherry-pick, merges,
tags, a worktree and a stash, but no `revert`.

**Why.** Part 0.1 says an advanced operation must have an honest place and
that inventing a sequence to tick the box is not acceptable. Every wrong state
this project produced — the second pass taking its ratio from an ICU line, the
scorer counting `IRDAI-List-I` as fabricated — was found and fixed *before* any
of it was committed, because commits now happen once at the end. Reverting a
commit that never carried the bug would be theatre.

**When the other option wins.** The moment a committed change drops an eval
score, revert it for real and record the revert here. The `git bisect` runbook
at the end of `GIT_COMMANDS.md` exists to find exactly that commit.

---

## D-03 — Sum-insured options come from the policy's own table where it has one

**Choice.** `GET /policies` returns `sum_insured_options` per policy:
star_health's nine rows read from its clause II.1 table, and the standard
3L/5L/10L/25L set for hdfc_ergo and niva_bupa.

**Why.** star_health prices the room limit by sum insured, so offering a value
its table does not carry would produce an audit that cannot resolve the room
line. The other two defer the room entitlement to the policy schedule, so their
table cannot supply the list and the syllabus set from Part 6 is used instead.

**When the other option wins.** If a fourth policy is uploaded that also prices
by sum insured, it gets its own list automatically. A hardcoded global list
would then be wrong.

---

## D-04 — PII is masked at the API edge, not left to `parse_bill`

**Choice.** `api/main.py` masks the bill text before the background job starts.

**Why.** `core/bill.parse_bill` already masks before the model sees anything,
but a job holds its bill text for as long as the process lives. An unmasked
patient name reaching the job store would outlive the request that carried it.
Masking twice is free and idempotent.

**When the other option wins.** Never, on this design. If the job store ever
stopped holding the bill text, edge masking would be redundant but still
harmless.

---

## D-05 — The frontend calls the gateway through one configurable base URL

**Choice.** `VITE_API_BASE` (default `http://localhost:8000`) is the only place
the API address appears.

**Why.** The same build has to work in three places: `npm run dev` against a
local uvicorn, docker-compose against the gateway container, and minikube
against a service. One env var covers all three.

**When the other option wins.** If the frontend were ever served from the same
origin as the API, the base could be `/api` and the variable could go.

---

## D-06 — The e2e test skips rather than fails when nothing is running

**Choice.** `tests/e2e/test_flow.py` checks the API health endpoint and the
frontend URL first, and calls `skipTest` with the exact command to start each.

**Why.** Part 6 asks for this directly, and the Jenkins Unit stage runs the same
suite as a developer's laptop. A hard failure there would mean the pipeline
fails for a reason unrelated to the change under test.

**When the other option wins.** In the Jenkins E2E stage specifically, a skip
could hide a real breakage — so that stage starts both services first, and
`BA_E2E_STRICT=1` turns the skips into failures.

---

## D-07 — Six services share `core/` as a library rather than duplicating it

**Choice.** Every Python service image copies the same `core/` package and
imports it. No logic is re-implemented per service.

**Why.** Part 7 requires it, and the audit rules are the product. Two copies of
`money.py` would eventually disagree, and the disagreement would show up as a
wrong rupee figure rather than as an error.

**When the other option wins.** If the services were owned by different teams
and released independently, a published shared package with a version number
would beat copying the directory into each image.

---

## D-08 — The eval threshold in Jenkins is 0.65, below the recorded 68.3%

**Choice.** `python eval/evaluate.py --quick --threshold 0.65`.

**Why.** Part 8 specifies 0.65 and says the threshold should sit just under the
current score. v5 is 68.3%, so a real regression of more than three points
fails the build while ordinary noise does not.

**When the other option wins.** Once the full 44-bill run is the recorded
number rather than the quick 10, the threshold should be re-derived from that
score instead.

---

## D-09 — flake8 runs in the build, ruff stays the linter for writing code

**Choice.** `build.py` uses the `python.flake8` plugin as Part 8 specifies, with
a `.flake8` config that turns off E203, W503, W504, E501 and E402. ruff remains
what the pre-commit hook runs and what `pyproject.toml` configures.

**Why.** PyBuilder's `analyze` task speaks flake8 and nothing else, and Jenkins
calls `pyb`. Running both without a config would have flake8 arguing with the
formatter over line breaks ruff already decided. The excluded codes are exactly
the ones every formatter disagrees with, plus line length, which ruff owns at
100 columns.

**When the other option wins.** If PyBuilder ever ships a ruff plugin, drop
flake8 and delete `.flake8`. Nothing else depends on it.

---

## D-10 — `api/` stays as a working monolith beside `services/`

**Choice.** Phase 10 added four services, and `api/main.py` was kept rather than
deleted. Both import the same `core/`, and `api/shared.py` holds the request
handling both use.

**Why.** The eval, the Selenium test and local development all want one process
on one port. Deleting the monolith would mean starting four containers to run a
40-bill evaluation, and `docker compose up` is not something to need before
`uv run python eval/evaluate.py` works. The rules live in `core/` either way, so
there is no second implementation to drift.

**When the other option wins.** If the two ever disagreed about a response
shape, the monolith should go and the eval should call the gateway. The shared
`api/shared.py` exists to stop that happening.

---

## D-11 — the coverage gate is 75%, measured at 79%

**Choice.** `coverage_threshold_warn = 75` in `build.py`.

**Why.** Part 8 says the threshold is what the suite achieves today, rounded
down, not an aspiration that fails on day one. The measured figure is 79% across
`core/`, `api/` and `services/`. Four points of headroom means ordinary movement
does not turn the build red while a real drop still does.

**When the other option wins.** Raise it when coverage genuinely rises —
`core/llm.py` at 23% and `core/ingest.py` at 30% are the two worth testing next,
and both would move the total several points.

## D-12 — bill lines are judged in parallel, with a per-backend width

**Decision.** `audit_lines` runs the first pass through a `ThreadPoolExecutor`.
`BA_AUDIT_WORKERS` sets the width; 0 means ask the backend, giving 4 on Groq
and 2 on Ollama.

**Why.** A Groq line is 6.1s, of which the model call is 1.7s and the rest is
retrieval and waiting. Sequentially that is a minute of mostly-idle time on a
ten-line bill. The lines are genuinely independent — nothing in the
anaesthetist's line reads the room rent verdict — so there is no ordering
constraint to violate.

**What it actually bought, measured on B01 with the cache off.** 222.6s at one
worker, 175.1s at two, 170.6s at four. So: 1.27x for the second worker, and
2.6% - noise - for the third and fourth, which also put the token bucket to
sleep for 37s. The default is 2 on both backends.

**Why it is only 1.27x.** Because the premise was wrong. The model is 6-8% of
a line's wall clock; retrieval is the rest, and one search already saturates
all ten cores. Adding workers contends for a resource that was never idle.
This is worth stating plainly: the obvious optimisation was applied to the
part of the system that was not the problem, and the measurement is what said
so. Making an audit materially faster now means a cheaper reranker - fewer
sentence windows, a smaller cross-encoder, or a rerank that runs once per line
instead of once per attempt, given 6 of 10 lines retry.

**What it does not change.** The second pass still runs after every line is
judged, because it reads all of them. Parallelising that would be a
correctness bug, not an optimisation.

**What it exposed.** On its first run, all four workers missed the same cold
`lru_cache` in `core/retrieve.py` and each opened its own Chroma client on the
same directory: `'RustBindingsAPI' object has no attribute 'bindings'`, then
`Could not connect to tenant default_tenant`, as a 500 from `/search`. The bug
predates the pool and was simply unreachable one line at a time. Fixed with a
lock over the lazy builders, and by warming the vector store and the
per-policy retrievers at startup rather than on the first request.

**Risk accepted.** Two properties are now only true because a test says so:
stable row order, and a progress counter that counts completions. Both fail
silently — the first as a flaky eval, the second as a progress bar that reads
"10 of 10" for a minute. `tests/test_workers.py` covers both.

## D-13 — the embedding weights ship in the image; the LLM does not

**Decision.** bge-base and bge-reranker are downloaded in the builder stage and
copied into the final image, with `HF_HOME=/opt/hf` and `HF_HUB_OFFLINE=1`.
Ollama's `qwen3:8b` stays a mounted volume, as PART 10 gotcha 8 requires.

**Why they are different.** The LLM is 5 GB and shared between services;
mounting it once is obviously right. The embedding weights are 1.6 GB and
belong to two services, and not baking them made a fresh container spend 606s
downloading before it could answer anything. That is a runtime dependency on
HuggingFace being reachable, on every restart, forever — and the target box has
no internet.

**Why offline mode, not just a warm cache.** Without `HF_HUB_OFFLINE=1` a
missing file silently degrades to a download. A developer machine has the cache
and would never see it; production would. With it set, an incomplete bake fails
the build, in the layer that ships, before the image exists.

**Cost and result.** 1.5 GB in retrieval-service (bge-base plus the reranker)
and 419 MB in ingestion-service (the embedder only). `docker compose up -d` to
`/ready` returning 200 went from 606s to **13.8s**, of which 10.5s is the load
itself. The trade is a bigger artefact against a pod that starts in fourteen
seconds and works with the network unplugged.

**Why the model names are duplicated in the Dockerfiles.** Copying `core/` into
the builder stage would put the download after it, so editing any core module
would re-fetch 1.6 GB on every build. `tests/test_services.py` asserts the
Dockerfile `ARG`s equal `settings.embedding_model` and `settings.reranker_model`
instead, which turns the drift into a test failure.

## D-14 — retrieval is cached by (query, policy); the rerank candidates are not halved

**Decision.** `core.retrieve._retrieve_documents` memoises the expensive half of
a search - hybrid retrieve, sub-chunk, rerank - on `(policy, query)`, bounded by
`BA_RETRIEVAL_CACHE_SIZE` (512) and invalidated whenever `clauses.json` changes.
`chroma_top_k` and `bm25_top_k` stay at 20.

**Why cache.** Retrieval is ~92% of an audit's wall clock. B01 through the
gateway with every LLM call already cached made **zero** model calls and still
took 207.0s; the same bill again, with the retrieval cache warm, took **0.3s**.
Both runs made zero model calls, so the 207 seconds were retrieval and nothing
else.

**What that number is not.** Re-running an identical bill is the best possible
case: every query matches. Across different bills the overlap is partial -
gloves, syringes and room rent recur, but the six retried lines rewrite their
queries and those rewrites mostly do not. 0.3s is the demo-replay ceiling, not
a typical audit. The first run costs what it always did.

**Why the index stamp.** Ingestion can rewrite `clauses.json` while
retrieval-service keeps serving. A hit computed against the old index could
cite a clause that no longer exists, which is the one failure this project
cannot ship. One `stat` per search is cheaper than reasoning about it.

**Why 10+10 was rejected.** Halving the rerank candidates is the single biggest
lever on that 92%, and it was tried: line accuracy went 68.3% -> 67.1% on the
quick eval. That is one line in 82, and citation accuracy moved the other way
(56.8% -> 58.0%), so it may be noise. It was still reverted. Deciding a
regression is noise *because* the change was wanted is exactly how a threshold
gets loosened, and this project's rules forbid it. If it is revisited, the full
44 bills decide, not the quick 10. Recorded in `eval/results.md`.

## D-15 — model inference is serialised behind one lock

**Decision.** `core.embeddings.INFERENCE_LOCK` is held across every forward
pass - `embed_query`, `embed_documents`, and the cross-encoder's `score`.

**Why.** On a Mac the models land on the MPS device and share one Metal command
queue. Two threads touching it is not slow, it aborts the process:

    failed assertion _status < MTLCommandBufferStatusCommitted
    at -[IOGPUMetalCommandBuffer setCurrentCommandEncoder:]

The eval died on bill one, every run, from the moment lines were judged in
parallel - first as SIGSEGV (139), then SIGABRT (134) once the load race was
fixed and the crash moved from loading to inference. The containers ship
CPU-only torch and never see it, which is precisely why it had to be fixed
rather than left for whoever next runs the eval on a laptop.

**Why serialising is affordable.** Measured, not assumed: two workers beat one
by 1.27x because a single search already saturates every core. The forward
passes were never meaningfully overlapping, so the lock costs close to nothing.

**Also fixed on the way.** `core.embeddings._load` had the same non-atomic
`lru_cache` as the retrievers, and `audit_lines` now warms retrieval explicitly
before starting the pool. Judging line one synchronously was tried first and
does not work: B01's first line is a non-payable item that settles on the fast
path without searching at all.

