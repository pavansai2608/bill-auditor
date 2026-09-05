#!/usr/bin/env bash
#
# Deploy this build to the local single-node cluster, and prove it landed.
#
# The Deploy stage used to run `kubectl apply -f k8s/` and stop there, which
# deployed nothing. Two reasons, and both are silent:
#
#   1. Jenkins builds into Docker Desktop's daemon. minikube runs its own
#      daemon inside the minikube container and cannot see across. The image
#      has to be carried over with `minikube image load`.
#   2. Every manifest pins `:latest`, so the Deployment spec is byte-identical
#      from one build to the next. `kubectl apply` compares specs, finds no
#      change, and starts no rollout. `imagePullPolicy: IfNotPresent` then
#      makes sure that even a restarted pod keeps the image it already has.
#
# So the stage reported success while the pods went on running whatever was
# loaded by hand, days earlier. On 2026-09-05 the pods were two days old and
# build 22 - finished an hour before - had never reached the cluster.
#
# The fix is to deploy the build-number tag rather than `:latest`. That is the
# only part of this that also makes the verification honest: comparing `:latest`
# against `:latest` passes whatever the pod is running, because the string never
# changes. `bill-auditor/gateway:23` either is what the pod reports or is not.
#
# The manifests in git are left alone. They are rendered through sed into a
# temporary directory with the tag substituted, so there is exactly one apply
# and one rollout - applying `:latest` first and then overriding it would
# supersede its own rollout on every build.
#
# BA_DEPLOY_SKIP_LOAD=<service> skips the image load for one service. It exists
# to prove this script fails when an image does not reach the node; nothing in
# the pipeline sets it.

set -euo pipefail

NS=bill-auditor
SERVICES="ingestion-service retrieval-service audit-service gateway frontend"
TAG="${BUILD_NUMBER:-latest}"
ROLLOUT_TIMEOUT="${BA_DEPLOY_TIMEOUT:-180s}"
SKIP_LOAD="${BA_DEPLOY_SKIP_LOAD:-}"

say() { printf '\n== %s\n' "$*"; }

# ---------------------------------------------------------------- preflight
for tool in kubectl minikube docker; do
  command -v "$tool" >/dev/null || { echo "deploy: $tool not on PATH" >&2; exit 1; }
done
kubectl cluster-info >/dev/null 2>&1 || { echo "deploy: kubectl reaches no cluster" >&2; exit 1; }

# Fail here rather than half way through a rollout.
for svc in $SERVICES; do
  docker image inspect "bill-auditor/${svc}:${TAG}" >/dev/null 2>&1 \
    || { echo "deploy: bill-auditor/${svc}:${TAG} was never built" >&2; exit 1; }
done

# ------------------------------------------------------- carry images across
say "loading images into minikube (tag ${TAG})"
for svc in $SERVICES; do
  if [ "$svc" = "$SKIP_LOAD" ]; then
    echo "  ${svc}: SKIPPED (BA_DEPLOY_SKIP_LOAD)"
    continue
  fi
  echo "  ${svc}"
  minikube image load "bill-auditor/${svc}:${TAG}"
done

# ------------------------------------------------------------------- apply
say "applying manifests with tag ${TAG}"
rendered="$(mktemp -d)"
trap 'rm -rf "$rendered"' EXIT
# Filename order matters: 00-namespace.yaml has to land before anything
# namespaced, which is why the manifests are numbered. cp keeps the names.
cp k8s/*.yaml "$rendered"/
sed -i.bak -E "s#(image: bill-auditor/[a-z-]+):latest#\1:${TAG}#" "$rendered"/*.yaml
rm -f "$rendered"/*.bak
kubectl apply -f "$rendered"

# ----------------------------------------------------------------- rollout
say "waiting for rollouts"
rollout_failed=""
for svc in $SERVICES; do
  if kubectl -n "$NS" rollout status "deploy/${svc}" --timeout="$ROLLOUT_TIMEOUT"; then
    continue
  fi
  echo "  ${svc}: rollout did not complete"
  rollout_failed="${rollout_failed} ${svc}"
done

# ------------------------------------------------------------------ verify
#
# The point of the whole change. A rollout can report success while a pod runs
# an older image, so read back what the pods are actually on.
#
# NOT `.status.containerStatuses[].image`. That field reports the tag the
# runtime resolved the image *ID* under, not the tag the pod was asked for, and
# the two differ whenever one image carries several tags - which is exactly
# what a rebuild that changes nothing produces. Measured on 2026-09-05: the
# tag-23 ReplicaSet `gateway-b5869f6d6` ran pods reporting
# `bill-auditor/gateway:22`, because :22 and :23 were one image and the kubelet
# named it by the older tag. The same field then reported `frontend:23` for a
# pod in ImagePullBackOff that was running nothing at all. Trusting it passed
# the one service that was broken and failed the four that were fine.
#
# What is sound is the pair: the pod's **spec** image is the tag this build
# asked for, and the container is **running and ready**. A skipped load cannot
# satisfy the second (ImagePullBackOff is never ready); a rollout that did not
# happen cannot satisfy the first (the surviving pod's spec carries the old
# tag). Terminating pods are excluded; anything else still on the old tag is a
# failure, not noise.
say "verifying pods run tag ${TAG}"
wrong=""
for svc in $SERVICES; do
  want="bill-auditor/${svc}:${TAG}"
  if ! kubectl -n "$NS" get pods -l "app=${svc}" -o json \
       | WANT="$want" SVC="$svc" python3 -c '
import json, os, sys

want, svc = os.environ["WANT"], os.environ["SVC"]
pods = [
    p for p in json.load(sys.stdin)["items"]
    if "deletionTimestamp" not in p["metadata"]
]
if not pods:
    print(f"  {svc}: FAIL - no pod (want {want})")
    sys.exit(1)

bad = 0
for p in pods:
    name = p["metadata"]["name"]
    spec_image = p["spec"]["containers"][0]["image"]
    status = (p["status"].get("containerStatuses") or [{}])[0]
    ready = bool(status.get("ready"))
    state = ", ".join(status.get("state", {})) or "no state"
    if spec_image != want:
        print(f"  {svc}: FAIL - {name} is on {spec_image}, want {want}")
        bad = 1
    elif not ready or "running" not in status.get("state", {}):
        reason = (status.get("state", {}).get("waiting", {}) or {}).get("reason", state)
        print(f"  {svc}: FAIL - {name} is on {want} but not running ({reason})")
        bad = 1

if bad:
    sys.exit(1)
print(f"  {svc}: ok - {len(pods)} pod(s) running {want}")
'; then
    wrong="${wrong} ${svc}"
  fi
done

# ------------------------------------------------------------------ verdict
if [ -n "$rollout_failed" ] || [ -n "$wrong" ]; then
  echo
  [ -n "$rollout_failed" ] && echo "deploy: rollout incomplete:${rollout_failed}" >&2
  [ -n "$wrong" ]          && echo "deploy: not running tag ${TAG}:${wrong}" >&2
  echo "deploy: FAILED" >&2
  exit 1
fi

say "deploy: all $(printf '%s' "$SERVICES" | wc -w | tr -d ' ') services running tag ${TAG}"
