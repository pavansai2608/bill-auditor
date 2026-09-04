#!/usr/bin/env bash
#
# The ownership rule, checked without starting anything.
#
# Regression for main #13, where the E2E stage killed Docker Desktop because it
# was listening on port 8000 and the stage assumed anything there was its own
# leftover. The Docker and Deploy stages then failed two stages later on a
# daemon this cleanup had removed.
#
#     uv run bash tests/e2e/test_ownership.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OWNED_PGIDS="/dev/null"
# shellcheck source=tests/e2e/lib_ports.sh
. "$ROOT/tests/e2e/lib_ports.sh"

fails=0
check() { # check DESCRIPTION EXPECTED ROLE COMMAND CWD
  local want="$2" role="$3"
  # Captured first: inside the stub bodies below, $4 and $5 would be the stub's
  # own arguments, not this function's. That mistake made every case report
  # "stranger" and four of them looked like passes.
  FAKE_COMMAND="$4"
  FAKE_CWD="$5"
  command_of() { echo "$FAKE_COMMAND"; }
  cwd_of() { echo "$FAKE_CWD"; }
  pgid_of() { echo "99999"; }
  if is_ours 1234 "$role"; then got=own; else got=stranger; fi
  if [ "$got" = "$want" ]; then
    printf '  ok    %s\n' "$1"
  else
    printf '  FAIL  %s (wanted %s, got %s)\n' "$1" "$want" "$got"; fails=$((fails+1))
  fi
}

echo "what this stage may kill:"
check "Docker Desktop on 8000 (main #13)" stranger api \
  "/Applications/Docker.app/Contents/MacOS/com.docker.backend services" "/"
check "an unrelated http.server" stranger api \
  "python3 -m http.server 8000" "/private/tmp"
check "a developer's npm run dev" stranger web \
  "node $ROOT/frontend/node_modules/.bin/vite --port 5173" "$ROOT/frontend"
check "our uvicorn from another checkout" stranger api \
  "/elsewhere/.venv/bin/uvicorn api.main:app --port 8000" "/elsewhere"
check "our own uvicorn" own api \
  "$ROOT/.venv/bin/python $ROOT/.venv/bin/uvicorn api.main:app --port 8000" "$ROOT"
check "our own vite preview" own web \
  "node $ROOT/frontend/node_modules/.bin/vite preview --port 5173" "$ROOT/frontend"

if [ "$fails" -eq 0 ]; then echo "ownership rule: all checks pass"; exit 0; fi
echo "ownership rule: $fails check(s) failed" >&2; exit 1
