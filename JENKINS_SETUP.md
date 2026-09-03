# Jenkins, from nothing, on macOS

Written for someone who has never opened Jenkins. Nothing is assumed. Every
command is meant to be pasted as written, and every field says exactly what to
type into it.

The pipeline is defined by `Jenkinsfile` at the repository root. Jenkins reads
that file out of the branch it is building, so the pipeline is versioned with
the code and there is nothing to configure in the UI beyond pointing Jenkins at
the repository.

What runs depends on the branch:

| Branch | Stages |
|---|---|
| `feature/*` | Build, Quality (Lint and Unit in parallel) |
| `develop` | ... plus Eval and E2E |
| `main` | ... plus Docker and Deploy |

**Section 8 is the one that matters.** It is a walkthrough where you break the
auditor's accuracy on purpose and watch Jenkins fail the build for it. A CI
stage that goes red because a model got worse is the distinctive thing here, and
it is the thing worth demonstrating.

---

## 1. Install Jenkins and start it

```bash
brew install jenkins-lts
brew services start jenkins-lts
```

It listens on <http://localhost:8080>. Give it a minute on first boot, then open
that address.

Where things live, for when you need them later:

| What | Where |
|---|---|
| Jenkins home (jobs, config, build history) | `~/.jenkins` |
| The initial admin password | `~/.jenkins/secrets/initialAdminPassword` |
| Per-build console logs | `~/.jenkins/jobs/<job>/branches/<branch>/builds/<n>/log` |
| Start / stop / restart | `brew services start|stop|restart jenkins-lts` |

If <http://localhost:8080> does not answer, `brew services list` will show
whether `jenkins-lts` is `started` or `error`.

## 2. Unlock it

The first screen asks for an administrator password:

```bash
cat ~/.jenkins/secrets/initialAdminPassword
```

Paste it in. On the next screen choose **Install suggested plugins** and wait —
it takes a few minutes. Then create your admin user when prompted. Use something
you will remember; there is no password reset worth the trouble.

## 3. Install the plugins this pipeline needs

**Manage Jenkins → Plugins → Available plugins.** Search for each by name, tick
it, then click **Install** and restart Jenkins when it offers.

| Plugin | Why this pipeline needs it |
|---|---|
| **Pipeline** | Runs a `Jenkinsfile` at all. Usually already there from "suggested". |
| **Pipeline: Multibranch** | Discovers branches and makes one job per branch. |
| **Git** | Clones the repository. |
| **Timestamper** | Backs `timestamps()` in the Jenkinsfile's `options`. Without it every build fails at startup. |
| **JUnit** | Renders the test results the `junit` step publishes. |
| **Workspace Cleanup** | Not required, but `Wipe Out Current Workspace` is the first thing to try when a build goes strange. |

**Blue Ocean** is optional and worth it for the demo in section 8 — it draws the
stages as a pipeline diagram, so a red Eval stage is obvious in a screenshot.

## 4. Give the agent the tools the build calls

Jenkins runs builds as your macOS user via a login shell, but **not** with your
interactive `~/.zshrc`, so anything installed in a non-standard place has to be
on `PATH`. The Jenkinsfile already prepends `/opt/homebrew/bin` for that reason.

Check each of these answers from a terminal:

```bash
uv --version          # the Python toolchain the build uses throughout
node --version        # E2E only
npm --version         # E2E only
ollama --version      # Eval and E2E only
docker --version      # main branch only
kubectl version --client   # main branch only
```

Install whatever is missing:

```bash
brew install uv node
brew install ollama && brew services start ollama
ollama pull qwen3:8b
```

**Nothing in Build, Lint or Unit needs Ollama, a Groq key, Docker or a cluster.**
That is deliberate and it is verified: the whole unit suite passes with Ollama
unreachable and no API key set. Stages that do need those things probe for them
first and mark themselves `NOT_BUILT` with the reason, rather than failing — a
stage that always fails teaches people to ignore red.

## 5. Credentials

**Manage Jenkins → Credentials → System → Global credentials (unrestricted) →
Add Credentials.**

**For a local clone, you need none.** The job points at a directory on this
machine, so there is nothing to authenticate.

If you later push this to GitHub and want Jenkins to pull from there:

| Field | Value |
|---|---|
| Kind | `Username with password` |
| Scope | `Global` |
| Username | your GitHub username |
| Password | a GitHub personal access token with `repo` scope |
| ID | `github-credentials` |
| Description | `GitHub read access for bill-auditor` |

The **ID** is the part that matters — that is the name you select in the job's
*Credentials* dropdown in section 6.

**The Groq API key is not required and the pipeline never asks for one.** The
Jenkinsfile pins `BA_LLM_BACKEND = 'ollama'`, because a 44-bill eval is roughly
400 model calls and would spend Groq's entire daily allowance. If you ever want
a stage to use Groq, add a **Secret text** credential with ID `ba-groq-api-key`
and wrap the step in `withCredentials`; nothing does today.

## 6. Create the multibranch pipeline job

**New Item** on the Jenkins home page.

- **Enter an item name:** `bill-auditor`
- Select **Multibranch Pipeline** (not "Pipeline", not "Freestyle project")
- Click **OK**

On the configuration page that follows, fill in exactly these:

**Branch Sources → Add source → Git**

| Field | What to type |
|---|---|
| Project Repository | `/Users/<you>/Desktop/bill-auditor` (or the GitHub URL) |
| Credentials | `- none -` for a local path; `github-credentials` for GitHub |

**Behaviours** — leave `Discover branches` as it is. That is what makes one job
per branch.

**Build Configuration**

| Field | What to type |
|---|---|
| Mode | `by Jenkinsfile` |
| Script Path | `Jenkinsfile` |

**Scan Multibranch Pipeline Triggers** — tick **Periodically if not otherwise
run** and set the interval to `1 hour`. A local path has no webhook to push
changes, so without this Jenkins only notices new commits when you scan by hand.

Click **Save**. Jenkins immediately scans the repository and starts a build for
every branch it finds a `Jenkinsfile` on.

**To scan again at any time:** open the `bill-auditor` job and click **Scan
Multibranch Pipeline Now** in the left-hand menu. This is also how you pick up
new branches.

**A local clone builds what is committed, not what is in your working tree.**
Jenkins clones the repository, so uncommitted edits are invisible to it. This
matters in section 8: the break has to be committed before Jenkins will see it.

## 7. What a green build looks like

Open the job, then the branch, then a build number, then **Console Output**.

On `feature/*` you should see four stages, and Quality contains two that run at
the same time:

```
[Pipeline] stage (Build)
+ uv sync --frozen --all-extras
+ uv run pyb clean
BUILD SUCCESSFUL

[Pipeline] parallel
[Pipeline] { (Lint)
+ uv run ruff check .
All checks passed!
+ uv run ruff format --check .
88 files already formatted
[Pipeline] { (Unit)
+ uv run pyb --no-venvs run_unit_tests
       Tasks: prepare [3429 ms] compile_sources [0 ms] run_unit_tests [66079 ms]
BUILD SUCCESSFUL
```

**A green Quality stage, specifically:** both Lint and Unit show `BUILD
SUCCESSFUL` or `All checks passed!`, the Unit stage reports roughly 369 tests,
and there is no `e2e.browser_flow` anywhere in its output. Unit takes about 70
seconds. If it takes four minutes and mentions `.pybuilder/plugins`, the
`--no-venvs` flag has been lost — see section 9, failure 1.

On `develop` you additionally get:

```
[Pipeline] stage (Eval)
+ uv run python eval/evaluate.py --quick --agent --second-pass --threshold 0.52
[1/10] B01 (star_health)
...
| Line accuracy (allowed within Rs 1) | 56.1% |
| **Fabricated clauses** | **0** |
```

and an E2E stage that starts the API and the frontend, runs four browser tests
and stops them again.

Every build, on every branch, archives `eval/results.md` — it appears as
**Build Artifacts** at the top of the build page.

## 8. Break the accuracy on purpose and watch the build go red

This is the demonstration. It takes about ten minutes end to end.

It breaks **the retrieval queries**, not the answer key and not the threshold.
That distinction is the whole point: the pipeline is not checking that a number
matches a number, it is checking that the auditor still works. The answer key is
untouched, the gate is untouched, and every unit test still passes — which is
exactly the kind of change that a normal test suite waves through.

### 8.1 Make the break

Open `core/agent.py` and find `QUERY_ANGLES`. Each rule type has three ways of
asking the same question, so a retry asks from a new angle rather than repeating
one that already missed. Replace **the whole dictionary** — all six rule types —
with queries that no longer mention the bill line at all:

```python
QUERY_ANGLES: dict[RuleType, list[str]] = {
    "room_rent": ["policy", "policy terms", "policy document"],
    "sub_limit": ["policy", "policy terms", "policy document"],
    "waiting_period": ["policy", "policy terms", "policy document"],
    "copay": ["policy", "policy terms", "policy document"],
    "non_payable": ["policy", "policy terms", "policy document"],
    "other": ["policy", "policy terms", "policy document"],
}
```

That is the entire change: one constant, and the `{item}` placeholder is gone
from every query. Retrieval now fetches near-arbitrary clauses for every line
that reaches the judge, so the judge reasons over wording that has nothing to do
with the item in front of it.

Keep the three entries in each list **distinct**. A unit test asserts that three
consecutive attempts produce three different queries, and if you collapse them
to one string that test fails — which would turn the Unit stage red and spoil
the demonstration, because the whole point is that Unit stays green.

Commit it on `develop` and push, or scan the job if it is a local clone:

```bash
git checkout develop
git add core/agent.py
git commit -m "refactor(agent): simplify the retrieval queries [BA-999]"
```

The commit message is deliberately innocuous. That is what this kind of change
looks like in a pull request.

### 8.2 What you will see in Jenkins

Open the job and click **Scan Multibranch Pipeline Now** if it does not start on
its own. Then open the `develop` build.

- **Build** — green.
- **Lint** — green. ruff has no opinion about what a query string says.
- **Unit** — **green, all 369 tests.** This is the part to point at. Nothing in
  the unit suite can tell that the auditor has been damaged, because no unit
  test runs a real bill against a real index.
- **Eval** — **red.** The console ends with:

  ```
  FAIL: line accuracy 0.488 is below the threshold 0.520
  ```

  and the stage exits 1, which fails the build. In Blue Ocean the Eval box is
  red and every box before it is green.
- **E2E** — never runs. Jenkins stops the pipeline at the first failed stage.

The build page shows **Build Artifacts → eval/results.md**, so the results table
from the failing build is archived alongside it.

The `post { failure { ... } }` block also prints:

```
If the Eval stage is the red one, read JENKINS_SETUP.md section 8 before changing the threshold.
```

That line exists because the tempting fix is to lower the threshold, and
lowering the threshold is how a project stops noticing that it is getting worse.

### 8.3 Revert

```bash
git revert --no-edit HEAD
```

Or undo the edit by hand — put the original dictionary back exactly:

```python
QUERY_ANGLES: dict[RuleType, list[str]] = {
    "room_rent": [
        "room rent limit per day eligible room category",
        "proportionate deduction associated medical expenses room category exceeded",
        "boarding nursing expenses hospital accommodation entitlement",
    ],
    "sub_limit": [
        "{item} sub-limit maximum payable",
        "{item} limit per policy period per treatment",
        "benefit limit expenses payable for {item}",
    ],
    "waiting_period": [
        "{item} waiting period specified disease exclusion",
        "months of continuous coverage before this treatment is covered",
        "listed conditions excluded until expiry of waiting period",
    ],
    "copay": [
        "co-payment percentage of claim amount",
        "share of claim borne by the insured person",
        "deductible co-pay applicable to this policy",
    ],
    "non_payable": [
        "{item} excluded expense not payable",
        "non-medical items excluded from the claim",
        "items for which coverage is not available",
    ],
    "other": [
        "{item} limit coverage",
        "expenses payable for {item} during hospitalization",
        "{item} exclusion or cap under this policy",
    ],
}
```

then commit, and scan again. Eval returns to green at 56.1%.

**Check afterwards that `core/agent.py` is clean**, because a half-reverted
`QUERY_ANGLES` is a quiet way to leave the auditor damaged:

```bash
git diff --stat            # expect no output
uv run python -m unittest discover -s tests
```

### 8.4 Why this break and not another

Five candidates were measured before settling on this one. It is worth knowing
that the obvious ones do not work, because someone repeating this demo will
reach for them:

| Change | Result | Why it is unsuitable |
|---|---|---|
| `num_ctx` 8192 → 2048 | 56.1%, unchanged | The prompts on these bills fit in 2048; no effect at all |
| `chroma_top_k`/`bm25_top_k` 20 → 2 | — | Fails a retrieval unit test, so **Unit** goes red, not Eval |
| `rerank_top_n` 3 → 1 | 69.5% | Accuracy went *up* |
| `max_attempts` 3 → 1 | — | Fails four unit tests |
| Judge prompt, `basis` line | 54.9% | A real drop, but still above the gate |
| `QUERY_ANGLES`, only the `other` entry | 52.4% | 43 of 82 — one line above the gate, still green |

The chosen break — all six angle lists — measures **48.8%**, comfortably under
the gate, with all 369 unit tests still passing. It is the only candidate of the
six that leaves the entire unit suite green while putting line accuracy under
the threshold, which is precisely the failure mode the Eval stage exists to
catch.

## 9. Failures you will actually hit

These three are not hypothetical. They are what the first real run of this
pipeline did, on `develop` and `main`, and each one is fixed in the committed
`Jenkinsfile` and `build.py`.

### Failure 1 — `FileExistsError` or `OSError` under `.pybuilder/plugins`

```
develop: FileExistsError: [Errno 17] File exists:
         .../.pybuilder/plugins/cpython-3.14.6.final.0/.../pip/_vendor/tomli_w
main:    OSError: [Errno 22] Invalid argument:
         .../.pybuilder/plugins/.../pip-26.2.1.dist-info/licenses/...
```

**What it means.** Two symptoms of one race. Lint and Unit run in parallel in
the same workspace, and PyBuilder was seeding its own virtualenvs under
`.pybuilder/plugins/...` in both stages at once, into the same directory.

**The fix, already applied.** Two parts:

- `pyb --no-venvs` — PyBuilder uses the interpreter it is already running under
  instead of building environments. The Build stage already installed everything
  into `.venv` with uv, so those environments were redundant as well as racy.
- Lint no longer uses PyBuilder at all. It runs `ruff`, which touches nothing
  PyBuilder owns, so the two stages share no state whatsoever.

**Parallelism was never the bug.** A shared cache was. The stages are still
parallel.

**One prerequisite worth knowing:** `--no-venvs` makes PyBuilder install its
plugin packages into the active virtualenv using pip, and uv does not put pip in
one. `pip` is therefore in the `dev` dependency group. Without it the stage
fails with `No module named 'pip'`.

### Failure 2 — the browser test runs inside the Unit stage

```
[ERROR] Test has error:
e2e.test_flow.AuditFlowTest.test_a_pasted_bill_produces_a_cited_report
```

**What it means.** That test drives a real browser against a running API and
frontend. It cannot pass in a stage where neither is up, and it is why `main`
went red after 233 tests.

**The cause.** `build.py` carried a comment saying the Selenium test was kept out
of the unit task — but nothing in the code did that. PyBuilder finds test
modules with `os.walk` and matches on **file name only**, so `tests/e2e/` cannot
be excluded by a glob and PyBuilder offers no exclusion property at all.

**The fix, already applied.** The module was renamed
`tests/e2e/test_flow.py` → `tests/e2e/browser_flow.py`. The `test_*` glob no
longer matches it, so neither `pyb run_unit_tests` nor `unittest discover`
collects it, and it runs only in the E2E stage where the services are up:

```bash
uv run python -m unittest tests.e2e.browser_flow
```

Nothing about the test itself changed. It still has four cases and they all
still pass.

### Failure 3 — `develop` exits with code -11

```
Unit stage exited with code -11
```

**What it means.** SIGSEGV. On a Mac, torch puts the embedder and the reranker
on the MPS device, and two threads touching one Metal command queue aborts the
process.

**The fix, already applied.** `BA_TORCH_DEVICE = 'cpu'` is set in the
Jenkinsfile's `environment` block, so CI never touches the GPU. CI has to be
reproducible, and a Metal command queue on a laptop is not. It costs about 1.7x
on embedding time and changes no result — cpu and mps agree to five decimals and
produce identical rankings.

### Other things that go wrong

| Symptom | Cause and fix |
|---|---|
| `uv: command not found` | `PATH` in the Jenkinsfile does not reach your Homebrew. Check `which uv` and add its directory. |
| A third of the suite fails on `ModuleNotFoundError` | `uv sync --frozen` without `--all-extras`. The base group has neither chromadb nor sentence-transformers. |
| Eval stage says `Eval skipped: no Ollama` and the build is **yellow** | Ollama is not running. `brew services start ollama`. Yellow, not red, is deliberate: the gate did not run, and that is different from failing. |
| E2E hangs then fails | The frontend never came up. Look for `npm ci` errors; `cd frontend && npm ci` by hand to see it properly. |
| `Docker skipped` / `Deploy skipped`, build yellow | No Docker daemon or no reachable cluster on the agent. Expected on a machine that has neither. |
| `timestamps()` errors at startup | The Timestamper plugin is not installed. See section 3. |
| Build uses old code | Jenkins builds what is committed. Commit, then **Scan Multibranch Pipeline Now**. |

## 10. Speed

A `feature/*` build is about two minutes. `develop` adds roughly five for Eval
and three for E2E.

The eval is slow because it is real: ten bills, each line through retrieval and
an 8B model. It is deliberately the `--quick` subset for that reason — the full
44-bill run takes about 40 minutes and does not belong in CI. Model calls are
cached to disk by prompt hash, so a re-run with no code change is much faster
than the first.

If Eval dominates your feedback loop, run it locally before pushing rather than
trimming the stage:

```bash
uv run python eval/evaluate.py --quick --agent --second-pass --threshold 0.52
```
