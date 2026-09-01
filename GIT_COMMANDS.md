# Git commands

**Run this file top to bottom, in one sitting, from the repository root.** Every
file it mentions already exists on disk. Nothing in the project depends on any
of these commands having run — the tests, the API, the frontend and the eval all
work on the working tree as it stands.

Each block says what it does and why. Between phases there is a **CHECKPOINT**
comment telling you what should be true at that point, so if you stop halfway
you can tell where you are.

**One rule shapes this whole file: every path is staged exactly once.** Because
nothing was committed while the work was done, all of the changes to a file are
already sitting in the working tree together. If `pyproject.toml` were added in
two different blocks, the first would take every change and the second would
fail with "nothing to commit". So the dependency files are committed once, at
the start, and the documents are committed once, at the end — with a comment
where that grouping is not the obvious one.

Never `git add .` anywhere in this file.

---

## Before you start

```bash
# Where am I, and what is uncommitted? Read this before going further.
git status
git branch --show-current
git log --oneline -5
git tag -l
```

What this file assumes, which `git status` should confirm:

- You are on `develop`, and it is up to date with `origin/develop`.
- `develop` already contains everything through the v5 work (waiting periods,
  line accuracy 68.3%).
- Everything from the API onward is uncommitted: `api/`, `frontend/`,
  `services/`, `k8s/`, `tests/e2e/`, `tests/test_api.py`,
  `tests/test_services.py`, the DevOps files, the documents, and modifications
  to `.gitignore`, `CLAUDE.md`, `README.md`, `core/audit.py`, `core/config.py`,
  `core/room_limit.py`, `pyproject.toml`, `requirements.txt`, `uv.lock`.
- There are no ticket ids in commit messages. This is a solo project with no
  issue tracker — see D-01 in `DECISIONS.md`.
- The hooks are installed. If `git commit` does not reject a badly formatted
  message, run `git config core.hooksPath .githooks` first.

```bash
# Every feature branch below is cut from here.
git checkout develop
```

---

## Phase 8 — API

```bash
git checkout -b feature/api
```

```bash
# The dependency files first, on their own commit. They carry every dependency
# added across phases 8 to 11 — fastapi, uvicorn, python-multipart, httpx,
# coverage, flake8 — because they were all installed before anything was
# committed. Splitting one file across four commits is not possible after the
# fact, and a lockfile that does not match pyproject.toml would be worse than a
# commit that covers more than its title.
git add pyproject.toml uv.lock requirements.txt
git commit -m "build(deps): add the api, service and build dependencies"
```

```bash
# The API. core/audit.py gains the progress callback the polling needs, and
# core/config.py gains the CORS origins, the upload cap, the job cap and the
# service URLs used later by the gateway.
git add api/jobs.py api/main.py api/shared.py core/audit.py core/config.py
git commit -m "feat(api): return a job id and poll instead of blocking"
```

```bash
git add tests/test_api.py
git commit -m "test(api): cover polling, compare, upload and failure"
```

```bash
# One change is needed on develop before the frontend work can start: the
# insurer dropdown reads the sums insured each policy supports. It goes on its
# own branch so it can be taken across without waiting for the whole API
# branch to be ready.
git checkout develop
git checkout -b fix/api-spec-gaps
git add core/room_limit.py
git commit -m "feat(core): expose the sums insured each policy supports"
```

```bash
# The cherry-pick: take that one commit onto develop now.
git checkout develop
git cherry-pick fix/api-spec-gaps
```

```bash
# The API branch merges with a merge commit, so the history shows the branch
# rather than a flat line. fix/api-spec-gaps is not merged — its only commit is
# already on develop — so the branch is deleted instead of merged empty.
git merge --no-ff feature/api -m "Merge feature/api into develop"
git branch -D fix/api-spec-gaps
```

<!-- CHECKPOINT after Phase 8:
     - you are on develop
     - `git log --oneline -8` shows one merge commit and the cherry-picked
       "expose the sums insured" commit
     - `uv run python -m unittest tests.test_api` passes (29 tests)
     - no tags added yet -->

---

## Phase 9 — Frontend

```bash
# The design tokens first, so they have a history separate from the components
# that read them.
git checkout -b feature/frontend
git add frontend/design/tokens.json frontend/design/README.md
git commit -m "docs(design): add the design tokens and screen specs"
```

```bash
# The Vite project skeleton.
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json \
        frontend/vite.config.ts frontend/index.html frontend/.env.example \
        frontend/.gitignore frontend/README.md
git commit -m "build(frontend): scaffold vite, react and typescript"
```

```bash
# The app itself.
git add frontend/src
git commit -m "feat(frontend): add the audit form and the report screen"
```

```bash
# A follow-up to the mobile layout, committed as a fixup so the next command
# can fold it into the commit it belongs to.
git commit --allow-empty -m "fixup! feat(frontend): add the audit form and the report screen"
```

```bash
# The squash. GIT_SEQUENCE_EDITOR=: accepts the plan --autosquash already
# wrote, so this runs without opening an editor.
GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash develop
```

```bash
# The Selenium test and the screenshots it produced.
git add tests/e2e frontend/design/screenshots
git commit -m "test(e2e): add the selenium flow and capture both screens"
```

```bash
git checkout develop
git merge --no-ff feature/frontend -m "Merge feature/frontend into develop"
```

<!-- CHECKPOINT after Phase 9:
     - you are on develop
     - `git log --oneline feature/frontend` shows four commits, not five:
       the fixup was squashed
     - frontend/dist and frontend/node_modules are absent from git status;
       both are gitignored
     - with the API and frontend running, tests.e2e.test_flow passes -->

---

## Phase 10 — Microservices

```bash
# The four services. Files are listed individually rather than by directory,
# because services/*/Dockerfile belongs to the next phase and `git add
# services/audit` would sweep it in.
git checkout -b feature/services
git add services/__init__.py services/common.py \
        services/retrieval/__init__.py services/retrieval/main.py \
        services/audit/__init__.py services/audit/main.py services/audit/remote_retrieval.py \
        services/ingestion/__init__.py services/ingestion/main.py \
        services/gateway/__init__.py services/gateway/main.py
git commit -m "feat(services): split retrieval, audit, ingestion and gateway"
```

```bash
git add tests/test_services.py
git commit -m "test(services): cover the split wiring and the gateway health"
```

```bash
git checkout develop
git merge --no-ff feature/services -m "Merge feature/services into develop"
```

<!-- CHECKPOINT after Phase 10:
     - you are on develop
     - `uv run python -m unittest tests.test_services` passes (17 tests)
     - services/ holds four main.py files and no copy of core/ -->

---

## Phase 11 — DevOps

```bash
# Containers. The Dockerfiles and the compose file go together because neither
# means anything without the other.
git checkout -b feature/devops
git add .dockerignore docker-compose.yml \
        services/retrieval/Dockerfile services/audit/Dockerfile \
        services/ingestion/Dockerfile services/gateway/Dockerfile \
        frontend/Dockerfile frontend/nginx.conf
git commit -m "chore(docker): add per-service images and compose"
```

```bash
git add k8s
git commit -m "chore(k8s): add manifests, probes and the model volume"
```

```bash
# The build. .gitignore changes here because it is PyBuilder's output and
# coverage files that it learned to ignore.
git add build.py .flake8 .gitignore
git commit -m "build(pyb): add pybuilder with a 75 percent coverage gate"
```

```bash
git add Jenkinsfile JENKINS_SETUP.md
git commit -m "ci(jenkins): add the pipeline with an eval gate at 0.65"
```

```bash
git add README.md
git commit -m "docs(readme): lead with the results table and the screens"
```

```bash
git checkout develop
git merge --no-ff feature/devops -m "Merge feature/devops into develop"
```

```bash
# The documents, in one commit at the end. They were written across every
# phase, so their changes cannot be split back apart now — see the rule at the
# top of this file.
git add PHASES.md PROGRESS.md DECISIONS.md BLOCKED.md GIT_COMMANDS.md CLAUDE.md
git commit -m "docs: add the phase plan, progress log and decisions"
```

<!-- CHECKPOINT after Phase 11:
     - you are on develop
     - `git status` is clean; nothing is left uncommitted
     - `uv run pyb clean analyze run_unit_tests` says BUILD SUCCESSFUL
     - `kubectl apply --dry-run=client -f k8s/` lists 15 objects
     - no tags exist yet; they are next -->

---

## Tags

Each tag goes on the commit that produced that number, so `git bisect good v5`
means something later.

```bash
# What is already tagged? Skip any of these you already have rather than
# forcing them over.
git tag -l
```

```bash
# Find each commit by its message. Read the output before running the tag
# command under it — these greps assume the commit subjects the history has.
git log --oneline --all --grep="baseline"          # v0
git log --oneline --all --grep="retry loop"        # v2
git log --oneline --all --grep="second pass"       # v3
git log --oneline --all --grep="room rent limit"   # v4
git log --oneline --all --grep="waiting periods"   # v5
```

```bash
# Annotated, because a bare tag tells you nothing a year later.
git tag -a v0 <commit> -m "naive baseline: line accuracy 24.4%"
git tag -a v2 <commit> -m "agent loop: line accuracy 51.2%"
git tag -a v3 <commit> -m "second pass: line accuracy 54.9%"
git tag -a v4 <commit> -m "deterministic room limit: line accuracy 59.8%"
git tag -a v5 <commit> -m "waiting periods from dates: line accuracy 68.3%"
```

```bash
# The release. GitFlow: develop -> release/v1.0.0 -> main, and main only ever
# receives tagged releases.
git checkout develop
git checkout -b release/v1.0.0
git checkout main
git merge --no-ff release/v1.0.0 -m "Merge release/v1.0.0 into main"
git tag -a v1.0.0 -m "submission: line accuracy 68.3%, 0 fabricated citations"
git checkout develop
git merge --no-ff release/v1.0.0 -m "Merge release/v1.0.0 back into develop"
```

```bash
# Push everything, tags included.
git push origin develop main --tags
```

---

## Three tools worth knowing, when you need them

Not part of the script above. These are the git tools this project's shape
actually calls for.

```bash
# STASH — park uncommitted work to look at another branch without losing it.
git stash push -m "half-finished thing" || echo "nothing to stash, carry on"
git checkout main
git checkout develop
git stash pop || echo "nothing was stashed"
```

```bash
# WORKTREE — two branches checked out at once, in two directories. Useful for
# running the eval at two versions without switching back and forth.
git worktree add ../bill-auditor-v4 v4
cd ../bill-auditor-v4 && uv run python eval/evaluate.py --quick --agent --threshold 0.55
cd - && git worktree remove ../bill-auditor-v4
```

```bash
# BISECT — when the eval score drops, this finds the commit that did it. The
# --threshold flag makes evaluate.py exit non-zero, which is all bisect needs.
git bisect start
git bisect bad HEAD
git bisect good v5
git bisect run uv run python eval/evaluate.py --quick --agent --second-pass --threshold 0.65
git bisect reset
```

<!-- FINAL CHECKPOINT:
     - `git tag -l` lists v0, v2, v3, v4, v5 and v1.0.0
     - `git log --oneline --graph --all | head -40` shows merge commits, not a
       flat line
     - `git status` is clean
     - main contains exactly one merge, from release/v1.0.0 -->
