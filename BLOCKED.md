# Blocked

Things that need you. Everything else was built and verified.

---

## B-01 — RESOLVED. The stack runs on minikube

Cleared on 2026-09-03. `kubectl apply -f k8s/` deploys and every pod reaches
`1/1 Running`: ollama, ingestion-service, retrieval-service, audit-service,
gateway x2, frontend x2. `kubectl -n bill-auditor rollout status deploy/gateway`
exits 0, the gateway answers `/health` with 200, and the frontend answers 200
from inside the cluster. That is the Definition of Done item met.

Three things were wrong and all three are fixed:

- **The gateway image was built under the wrong name.** The Jenkins Docker stage
  looped over service directories and appended `-service` to each, producing
  `bill-auditor/gateway-service` while `k8s/50-gateway.yaml` asks for
  `bill-auditor/gateway`. The loop now lists image names explicitly.
- **minikube could not see any image.** It runs its own Docker daemon, separate
  from Docker Desktop where the images are built, and the manifests are
  `imagePullPolicy: IfNotPresent` - so every pod sat in `ImagePullBackOff`
  trying Docker Hub. The five images are now loaded with `minikube image load`.
- **The node ran out of memory.** ollama alone reserves 6Gi of ~12Gi
  allocatable, so `audit-service` and `retrieval-service` at two replicas each
  pushed the node to 99% and the frontend could never be scheduled. Both are now
  one replica, with the reason recorded in the manifests.

**The one caveat.** minikube here uses the **docker driver**, so the node IP
(192.168.49.2) is on a Docker network macOS cannot route to - the NodePorts are
not reachable from the host directly. Open the app through the tunnel instead:

```bash
minikube service frontend -n bill-auditor
minikube service gateway  -n bill-auditor --url
```

Rebuilding images requires loading them again, because the Jenkins Docker stage
builds into Docker Desktop:

```bash
for i in frontend gateway audit-service ingestion-service retrieval-service; do
  minikube image load "bill-auditor/${i}:latest"
done
```

---

## B-02 — RESOLVED. All five images build and the stack runs

Cleared on 2026-09-01. `docker compose build` produces all five images, all six
containers report healthy, and bill B01 was audited end to end through the
gateway: room rent capped at Rs 5,000/day and the proportionate deduction
applied to the associated medical expenses by the audit service, with the
clause index served from the shared volume by the retrieval service.

Four defects were found by actually running it, none of which syntax checking
could have caught:

- **Every Python image failed to build.** Line 3 of the generated
  `requirements.txt` is `-e .`, so the install builds this project too, but the
  builder stage copied only the metadata files. The four Dockerfiles now copy
  `src/` and `README.md` as well.
- **All 402 clauses were labelled `other`.** `BA_OLLAMA_BASE_URL` was set on
  `audit-service` only, so ingestion fell back to `localhost:11434` inside its
  own container and every labelling call was refused. Costly to spot because
  ingestion logs a warning and carries on by design. The k8s ConfigMap already
  supplied it to every pod, so this was compose-only.
- **The frontend was permanently `unhealthy` while serving pages correctly.**
  nginx listens on IPv4 only; busybox `wget` resolves `localhost` to `::1`
  first and is refused. The healthcheck now probes `127.0.0.1`.
- **The first audit died with `llama-server ... signal: killed`.** The Docker VM
  has 7.7 GB and another project's cluster was holding 2.5 GB of it, so
  `qwen3:8b` was OOM-killed. Not a code defect. Worked around locally with a
  gitignored `docker-compose.override.yml` pointing the audit service at the
  Mac's native Ollama; the committed stack stays self-contained and needs about
  12 GB given to Docker Desktop.

What has still not been measured here: build times and layer sizes under a cold
cache, and inference speed inside the container, since the audit that ran used
the host's Ollama.

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
