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
