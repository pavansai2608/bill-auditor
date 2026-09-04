#!/usr/bin/env bash
#
# Leave no server behind. Called from the E2E stage's `post { always { ... } }`,
# so it runs after a pass, a failure and an abort alike.
#
# `run_stage.sh` already takes its own process groups down on every exit path.
# This is the belt on top of that brace, and it exists because the thing that
# broke the stage for months was a server surviving into the next build: one
# orphaned `vite preview` answered the readiness curl of every run after it,
# and Selenium tested that instead of the build under test.
#
# It never fails the build. A cleanup step that can go red turns an honest test
# failure into a confusing one.
set -u
for port in "${@:-5173 8000}"; do
  pids="$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "freeing port $port, still held by: $pids"
    ps -o pid=,pgid=,command= -p $pids 2>/dev/null || true
    kill -KILL $pids 2>/dev/null || true
  fi
done
rm -f .api.pid .web.pid
exit 0
