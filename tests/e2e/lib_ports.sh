#!/usr/bin/env bash
#
# Who owns a port, and may this stage kill it?
#
# WHY THIS EXISTS
#
# The first version of the port-freeing logic assumed anything listening on
# 8000 was a leftover of its own. From main #13:
#
#     === port 8000 is already held by pid(s): 32061 - this is the leak, clearing it
#     32061 32008 /Applications/Docker.app/Contents/MacOS/com.docker.backend services
#
# It killed Docker Desktop. Two stages later the Docker stage found no daemon
# and Deploy found no cluster: **the pipeline killed its own dependency**, and
# it did so while reporting that it was cleaning up after itself.
#
# The assumption was never earned. A port number is not a claim of ownership.
# Killing an unknown process is worse than failing, because a failure is
# legible and a dead daemon three stages later is not.
#
# THE RULE
#
# A process may be killed only if this stage can positively identify it as its
# own. Two ways to earn that, and nothing else counts:
#
#   1. Its process group was recorded by an earlier run of `run_stage.sh`, in
#      `.e2e-logs/owned-pgids`.
#   2. Its command line is one this script starts *and* its working directory
#      is inside this repository.
#
# Anything else is a stranger. Strangers are named, with their command line,
# and the stage fails telling the operator to free the port or move it.
#
# This is ownership, not force. Do not "fix" a future clash by choosing a
# signal the other process survives - that is the same wrong assumption with a
# smaller blast radius.
#
# Sourced by run_stage.sh and free_ports.sh so the two cannot disagree about
# what ownership means.

# The commands this stage starts, and nothing else. Matched against the full
# command line of the listening process.
#
#   api  .venv/bin/python .venv/bin/uvicorn api.main:app --port 8000
#   web  node frontend/node_modules/.bin/vite preview --port 5173
#
# A `npm run dev` vite is deliberately NOT a match. It is a real server someone
# is using, it is not the preview server this stage starts, and killing it is
# the same mistake as killing Docker in a smaller coat.
_role_pattern() {
  case "$1" in
    api) printf 'uvicorn' ;;
    web) printf 'vite' ;;
    *) printf '\0' ;;
  esac
}

_role_second() {
  case "$1" in
    api) printf 'api.main:app' ;;
    web) printf 'preview' ;;
    *) printf '\0' ;;
  esac
}

listeners() {
  # Every pid listening on a port. lsof exits 1 when nothing matches, which is
  # not an error here.
  lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null || true
}

pgid_of() {
  ps -o pgid= -p "$1" 2>/dev/null | tr -d ' ' || true
}

command_of() {
  ps -o command= -p "$1" 2>/dev/null || true
}

cwd_of() {
  lsof -a -p "$1" -d cwd -Fn 2>/dev/null | grep '^n' | cut -c2- | head -1 || true
}

recorded_pgids() {
  [ -f "$OWNED_PGIDS" ] && cat "$OWNED_PGIDS" 2>/dev/null || true
}

remember_pgid() {
  mkdir -p "$(dirname "$OWNED_PGIDS")"
  echo "$1" >> "$OWNED_PGIDS"
}

is_ours() {
  # is_ours PID ROLE -> 0 when this stage may kill it
  local pid="$1" role="$2" command cwd recorded

  # 1. A process group this script recorded on an earlier run.
  local mine; mine="$(pgid_of "$pid")"
  if [ -n "$mine" ]; then
    for recorded in $(recorded_pgids); do
      [ "$mine" = "$recorded" ] && return 0
    done
  fi

  # 2. Our command, running out of our workspace. Both halves are required:
  #    the command alone would match a copy of this project in another
  #    checkout, and the directory alone would match anything a developer
  #    happens to be running here.
  command="$(command_of "$pid")"
  cwd="$(cwd_of "$pid")"
  case "$command" in
    *"$(_role_pattern "$role")"*) ;;
    *) return 1 ;;
  esac
  case "$command" in
    *"$(_role_second "$role")"*) ;;
    *) return 1 ;;
  esac
  case "$cwd" in
    "$ROOT"|"$ROOT"/*) return 0 ;;
    *) return 1 ;;
  esac
}

describe_holder() {
  local pid="$1"
  printf '  pid %s  pgid %s\n' "$pid" "$(pgid_of "$pid")"
  printf '    command: %s\n' "$(command_of "$pid")"
  printf '    cwd    : %s\n' "$(cwd_of "$pid")"
}

# free_port PORT ROLE ENVVAR
#
# Returns 0 when the port is clear. Returns 1, having explained itself, when a
# process this stage does not own is holding it. The caller decides what to do
# about that; nothing here kills a stranger.
free_port() {
  local port="$1" role="$2" envvar="$3" pid pids strangers=""

  pids="$(listeners "$port")"
  [ -z "$pids" ] && return 0

  for pid in $pids; do
    if is_ours "$pid" "$role"; then
      echo "port $port: pid $pid is this stage's own $role server, clearing it"
      kill -TERM "$pid" 2>/dev/null || true
    else
      strangers="$strangers $pid"
    fi
  done

  if [ -n "$strangers" ]; then
    echo "" >&2
    echo "port $port is held by a process this stage does not own:" >&2
    for pid in $strangers; do describe_holder "$pid" >&2; done
    cat >&2 <<EOF

Not killing it. This stage once assumed anything on this port was its own
leftover and killed Docker Desktop, which took the Docker and Deploy stages
down with it two stages later.

Either stop that process yourself, or run the stage on a different port:

    $envvar=<port> tests/e2e/run_stage.sh
EOF
    return 1
  fi

  # Ours, and asked to stop. Give it a moment, then insist.
  local waited=0
  while [ -n "$(listeners "$port")" ] && [ "$waited" -lt 10 ]; do
    sleep 1
    waited=$((waited + 1))
  done
  for pid in $(listeners "$port"); do
    if is_ours "$pid" "$role"; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  sleep 1

  pids="$(listeners "$port")"
  if [ -n "$pids" ]; then
    echo "" >&2
    echo "port $port is still held after TERM and KILL:" >&2
    for pid in $pids; do describe_holder "$pid" >&2; done
    return 1
  fi
  return 0
}
