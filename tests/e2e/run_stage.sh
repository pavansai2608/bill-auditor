#!/usr/bin/env bash
#
# Start both halves of the app, prove they are the ones this run started, run
# the browser test, and take the whole process group down afterwards.
#
# WHY THIS EXISTS
#
# The E2E stage never tested the build it was given. From develop #17:
#
#     16:27:20  + curl -sf http://localhost:5173
#     16:27:20  + break
#
# Port 5173 answered one second into the stage. Nothing this run started could
# be up that fast - it had not finished `npm ci` yet. The readiness loop asked
# "is something listening", a leftover `vite preview` from an earlier build
# said yes, and Selenium then drove a stale frontend until it timed out looking
# for an element the old bundle did not have.
#
# main #11 shows the same defect passing:
#
#     + npx vite preview --port 5173
#     error when starting preview server:
#     Error: Port 5173 is already in use
#     ...
#     Ran 4 tests in 10.732s
#     OK
#
# The preview server failed to start, the failure was swallowed because it ran
# in a background subshell, the readiness curl found the survivor, and four
# tests passed against a build nobody had made. **Green and red for the same
# wrong reason. Neither result was real.**
#
# The survivor kept coming back because cleanup killed the wrong process.
# `( cd frontend && ... npx vite preview ) &` records the subshell's pid;
# `npx` then forks vite as a child. `kill <subshell>` leaves that child holding
# the port. Every build donated one more orphan to the next.
#
# THE THREE CHECKS
#
# 1. The port is freed before anything starts, and if it cannot be freed the
#    stage fails rather than working around it.
# 2. Each server is started as a process-group leader (`set -m`), so a build
#    failure is visible and cleanup can signal the group rather than one pid.
# 3. Readiness is not "something answered". Two independent proofs:
#
#    * **The process listening on the port is in this run's process group.**
#      This is the one a survivor cannot satisfy. A leftover from an earlier
#      build belongs to a process group whose leader is a shell that exited
#      builds ago; it can never be in a group created seconds ago by this
#      script. Answering the port is not enough, serving the right bytes is not
#      enough - it has to *be* our process.
#    * **The bytes served carry this run's build stamp.** A random token is
#      written into `dist/` after the build and fetched back over HTTP. This
#      proves the server is serving a build that completed in this run.
#
#    Neither alone is sufficient, which is why both are here. The stamp alone
#    cannot catch a survivor: Jenkins keeps its workspace, so an orphaned server
#    serves the same `frontend/dist` directory this run just rebuilt, and would
#    hand back the new stamp quite happily. The process-group check alone cannot
#    catch a server that is ours but is serving a half-written `dist/`.
#
# Usage:  tests/e2e/run_stage.sh
# Env:    BA_E2E_API_PORT (8000), BA_E2E_WEB_PORT (5173), BA_E2E_SKIP_BUILD

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

API_PORT="${BA_E2E_API_PORT:-8000}"
WEB_PORT="${BA_E2E_WEB_PORT:-5173}"
LOGS="$ROOT/.e2e-logs"
STAMP_FILE="$ROOT/frontend/dist/ba-build-stamp.txt"
# Long enough for a cold uvicorn and a vite preview, short enough that a hang
# fails the stage instead of holding the executor for the build timeout.
READY_TIMEOUT="${BA_E2E_READY_TIMEOUT:-90}"

API_PGID=""
WEB_PGID=""

say() { printf '\n=== %s\n' "$*"; }
die() { printf '\nE2E STAGE FAILED: %s\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------
# ports and process groups
# --------------------------------------------------------------------------

listeners() {
  # Every pid listening on a port. lsof is on both the macOS and Linux agents;
  # `|| true` because it exits 1 when nothing matches, which is not an error.
  lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null || true
}

pgid_of() {
  ps -o pgid= -p "$1" 2>/dev/null | tr -d ' ' || true
}

free_port() {
  local port="$1" pids
  pids="$(listeners "$port")"
  [ -z "$pids" ] && return 0

  say "port $port is already held by pid(s): $pids - this is the leak, clearing it"
  # shellcheck disable=SC2086
  ps -o pid=,pgid=,command= -p $pids 2>/dev/null || true
  # shellcheck disable=SC2086
  kill -TERM $pids 2>/dev/null || true

  local waited=0
  while [ -n "$(listeners "$port")" ] && [ "$waited" -lt 10 ]; do
    sleep 1
    waited=$((waited + 1))
  done
  if [ -n "$(listeners "$port")" ]; then
    # shellcheck disable=SC2046
    kill -KILL $(listeners "$port") 2>/dev/null || true
    sleep 2
  fi

  pids="$(listeners "$port")"
  [ -z "$pids" ] || die "port $port is still held by $pids after TERM and KILL.
Something is running that this stage may not kill. Free it by hand and re-run;
carrying on would test whatever that process is serving, which is the exact
defect this script exists to stop."
}

owned_by_us() {
  # Is every listener on this port inside the process group we started?
  local port="$1" want="$2" pid actual
  local pids; pids="$(listeners "$port")"
  [ -n "$pids" ] || return 1
  for pid in $pids; do
    actual="$(pgid_of "$pid")"
    [ "$actual" = "$want" ] || return 1
  done
  return 0
}

cleanup() {
  local status=$?
  for pgid in "$WEB_PGID" "$API_PGID"; do
    [ -n "$pgid" ] || continue
    # Negative pid signals the whole group, which is what takes npx's child
    # with it. Killing the pid alone is what orphaned a vite preview on every
    # previous build.
    kill -TERM "-$pgid" 2>/dev/null || true
  done
  sleep 2
  for pgid in "$WEB_PGID" "$API_PGID"; do
    [ -n "$pgid" ] || continue
    kill -KILL "-$pgid" 2>/dev/null || true
  done
  # Whatever happened above, the ports must be clear for the next build. This
  # is the promise the old cleanup did not keep.
  for port in "$WEB_PORT" "$API_PORT"; do
    local leftover; leftover="$(listeners "$port")"
    if [ -n "$leftover" ]; then
      echo "cleanup: port $port still held by $leftover, killing" >&2
      # shellcheck disable=SC2086
      kill -KILL $leftover 2>/dev/null || true
    fi
  done
  exit $status
}
trap cleanup EXIT INT TERM

# Job control, so each background command becomes its own process-group leader
# and its pid is usable as a group id.
set -m

mkdir -p "$LOGS"
rm -f "$LOGS"/*.log

# --------------------------------------------------------------------------
# 1. clear the ground
# --------------------------------------------------------------------------

say "freeing ports $API_PORT and $WEB_PORT"
free_port "$API_PORT"
free_port "$WEB_PORT"

# --------------------------------------------------------------------------
# 2. build, then stamp the build
# --------------------------------------------------------------------------

STAMP="$(date +%s)-$$-$RANDOM"

if [ -n "${BA_E2E_SKIP_BUILD:-}" ]; then
  say "skipping the frontend build (BA_E2E_SKIP_BUILD set)"
  [ -d "$ROOT/frontend/dist" ] || die "no frontend/dist to serve"
else
  say "building the frontend"
  # Not backgrounded: a build failure must fail the stage here, loudly, rather
  # than becoming a server that never starts and a readiness loop that finds
  # somebody else's.
  ( cd frontend && npm ci && npm run build ) || die "the frontend build failed"
fi

echo "$STAMP" > "$STAMP_FILE"
say "build stamp for this run: $STAMP"

# --------------------------------------------------------------------------
# 3. start both halves as process-group leaders
# --------------------------------------------------------------------------

say "starting the API on $API_PORT"
uv run uvicorn api.main:app --port "$API_PORT" > "$LOGS/api.log" 2>&1 &
API_PGID=$!

say "starting vite preview on $WEB_PORT"
( cd frontend && exec npx vite preview --port "$WEB_PORT" --strictPort ) \
  > "$LOGS/web.log" 2>&1 &
WEB_PGID=$!

# --strictPort makes vite exit rather than silently move to 5174. Without it a
# server that could not have the port it was asked for would keep running on a
# port nothing checks, and the readiness curl would go on talking to the
# survivor - which is main #11 exactly.

# --------------------------------------------------------------------------
# 4. readiness, proved three ways
# --------------------------------------------------------------------------

wait_for() {
  local what="$1" pgid="$2" port="$3" probe="$4" waited=0
  while [ "$waited" -lt "$READY_TIMEOUT" ]; do
    if ! kill -0 "$pgid" 2>/dev/null; then
      echo "--- $what log ---" >&2
      cat "$LOGS/$5" >&2 || true
      die "$what exited before it was ready. Its log is above."
    fi
    if eval "$probe" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  echo "--- $what log ---" >&2
  cat "$LOGS/$5" >&2 || true
  die "$what was not ready in ${READY_TIMEOUT}s. Its log is above."
}

say "waiting for the API"
wait_for "the API" "$API_PGID" "$API_PORT" \
  "curl -sf http://localhost:$API_PORT/health" "api.log"

say "waiting for the frontend"
wait_for "vite preview" "$WEB_PGID" "$WEB_PORT" \
  "curl -sf http://localhost:$WEB_PORT/ba-build-stamp.txt" "web.log"

# Proof 1: the process holding the port is ours.
if ! owned_by_us "$WEB_PORT" "$WEB_PGID"; then
  echo "--- who actually holds port $WEB_PORT ---" >&2
  # shellcheck disable=SC2046
  ps -o pid=,pgid=,command= -p $(listeners "$WEB_PORT") 2>/dev/null >&2 || true
  die "port $WEB_PORT is answering, but not from this run's process group ($WEB_PGID).
Something that outlived an earlier build is serving an older frontend. That is
what made develop #17 red and main #11 green without either testing anything."
fi

if ! owned_by_us "$API_PORT" "$API_PGID"; then
  die "port $API_PORT is answering, but not from this run's process group ($API_PGID)."
fi

# Proof 2: the bytes on the wire came from the build this run made.
SERVED="$(curl -sf "http://localhost:$WEB_PORT/ba-build-stamp.txt" | tr -d '[:space:]')"
if [ "$SERVED" != "$STAMP" ]; then
  die "the frontend on $WEB_PORT is serving build stamp '$SERVED', not this run's '$STAMP'."
fi

say "both halves are this run's own: web pgid $WEB_PGID, api pgid $API_PGID, stamp $STAMP"

# --------------------------------------------------------------------------
# 5. the test
# --------------------------------------------------------------------------

say "running the browser test"
BA_E2E_STRICT=1 uv run python -m unittest tests.e2e.browser_flow
