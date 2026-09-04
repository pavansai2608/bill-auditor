#!/usr/bin/env bash
#
# Leave none of *our* servers behind. Called from the E2E stage's
# `post { always { ... } }`, so it runs after a pass, a failure and an abort.
#
# It kills only what this stage can prove it started - see `lib_ports.sh` for
# the rule and for what the previous version cost. That version killed whatever
# held the port, and on main #13 that was Docker Desktop; the Docker and Deploy
# stages then failed two stages later on a daemon this cleanup had removed.
#
# A stranger on the port is reported and left alone. This script never fails the
# build: a cleanup step that can go red turns an honest test failure into a
# confusing one, and the stage itself already refuses to run against a port it
# does not own.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS="$ROOT/.e2e-logs"
OWNED_PGIDS="$LOGS/owned-pgids"

# shellcheck source=tests/e2e/lib_ports.sh
. "$ROOT/tests/e2e/lib_ports.sh"

API_PORT="${BA_E2E_API_PORT:-8000}"
WEB_PORT="${BA_E2E_WEB_PORT:-5173}"

for spec in "$API_PORT:api" "$WEB_PORT:web"; do
  port="${spec%%:*}"
  role="${spec##*:}"
  for pid in $(listeners "$port"); do
    if is_ours "$pid" "$role"; then
      echo "cleanup: killing this stage's $role server on port $port (pid $pid)"
      kill -KILL "$pid" 2>/dev/null || true
    else
      echo "cleanup: leaving port $port alone, it is not ours:"
      describe_holder "$pid"
    fi
  done
done

rm -f "$ROOT/.api.pid" "$ROOT/.web.pid"
exit 0
