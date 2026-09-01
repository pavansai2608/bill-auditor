# Blocked

Things that need you. Everything else was built and verified.

---

## B-01 — minikube is not installed on this machine

**What is affected.** `k8s/` was written and every manifest is validated with
`kubectl apply --dry-run=client`, but nothing was actually deployed. The
Definition of Done item "`kubectl apply -f k8s/` deploys on minikube" is
therefore unverified.

**What I need from you.**

```bash
brew install minikube
minikube start --memory=8192 --cpus=4
kubectl apply -f k8s/
kubectl get pods -w
```

`kubectl` itself is installed (v1.36.3), so only minikube is missing.

---

## B-02 — the Docker daemon was not available to build images

**What is affected.** Dockerfiles and `docker-compose.yml` are written and their
syntax is checked, but no image was built here, so build times and layer sizes
are estimates.

**What I need from you.** Start Docker Desktop, then:

```bash
docker compose build
docker compose up -d
docker compose ps
```

Note `docker-compose` (the old standalone binary) is not on this machine;
`docker compose` (the v2 plugin) is what the commands use.

---

## B-03 — Jenkins has never been run against this repo

**What is affected.** `Jenkinsfile` and `JENKINS_SETUP.md` are written, but no
pipeline has executed, so no stage has been observed passing or failing.

**What I need from you.** Follow `JENKINS_SETUP.md` end to end once. The step
that matters most is the Eval stage: make a change that drops line accuracy
below 0.65 and confirm the build goes red. That behaviour is the most
distinctive thing in the pipeline and it should be seen working at least once.

---

## B-04 — the eval numbers cover 10 bills, not all 44

**What is affected.** Every row in `eval/results.md` is a `--quick` run.

**What I need from you.** One full run, when you have 45 minutes free:

```bash
uv run python eval/evaluate.py --agent --second-pass --version v5-full --write
```

It appends a row rather than replacing anything. This is recorded in
`KNOWN_LIMITATIONS.md` too.

---

## B-05 — Stitch was not available to generate the two screens

**What is affected.** Phase 9 asked for the screens to be designed in Stitch
first, with its tokens and exported code saved to `frontend/design/`. Stitch was
not reachable from the environment this was built in, so nothing came out of it.

**What was done instead.** The design system was written out explicitly to the
same brief before any component was built. `frontend/design/tokens.json` holds
the colours, type scale, spacing, radii and shadows;
`frontend/design/README.md` holds the screen layouts, the component specs and
the loading, error and empty states. `frontend/src/styles.css` mirrors those
token names one-for-one as CSS variables, so nothing in the interface is a value
that was eyeballed.

**What I need from you.** If you want the Stitch version specifically, generate
the two screens there and drop its tokens into `frontend/design/tokens.json`,
keeping the key names. The stylesheet reads `--colour-*`, `--space-*` and
`--text-*` variables that match those keys exactly, so the whole interface picks
up the new values without a single component changing.

The screenshots in `frontend/design/screenshots/` are of the built interface
rather than of a mockup, which is arguably the more useful artefact either way.
