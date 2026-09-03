"""Where a real audit's minutes go, measured through the gateway.

`where_time_goes.py` times one line in this process and reports 6.1s on Groq.
A bill through the UI took seven minutes. Both numbers cannot be right about
the same system, and the difference is everything the single-line tool does
not exercise: the gateway hop, the running container's actual backend, the
number of lines in flight, and retries.

This runs one real bill end to end and reports:

    per-line wall clock      from the progress counter, timestamped
    lines in flight          inferred from how the counter climbs
    attempts per line        from the report's own trace
    which lines retried      the ones that paid for retrieval more than once

    uv run python eval/audit_profile.py --bill B01
    BA_AUDIT_WORKERS=4 docker compose up -d --force-recreate audit-service

The backend the container actually used is not visible from out here; ask it:

    docker compose exec audit-service python -c \\
      "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/stats').read().decode())"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_bill(name: str) -> dict:
    """The text fixture the UI's paste box would receive, plus its inputs."""
    raw = json.loads((ROOT / "eval" / "bills" / f"{name}.json").read_text())
    text_file = ROOT / "eval" / "bills" / "text" / f"{name}.txt"
    return {
        "bill_text": text_file.read_text() if text_file.exists() else raw["bill_text"],
        "policy": raw["policy"],
        "sum_insured": raw["sum_insured"],
        "policy_start_date": raw.get("policy_start_date"),
        "admission_date": raw.get("admission_date"),
    }


def run(base: str, payload: dict, poll_s: float) -> tuple[dict, list[tuple[float, int]]]:
    """Submit, then poll, keeping a timestamp for every change in `done`."""
    with httpx.Client(timeout=30) as http:
        started = time.monotonic()
        # The gateway takes multipart form fields, not JSON: the same endpoint
        # accepts an uploaded PDF, so the whole body is a form. Only the
        # audit-service behind it speaks JSON, and it is not published.
        form = {k: str(v) for k, v in payload.items() if v is not None}
        created = http.post(f"{base}/audit", data=form)
        created.raise_for_status()
        job_id = created.json()["job_id"]
        print(f"job {job_id}")

        marks: list[tuple[float, int]] = []
        last = -1
        while True:
            time.sleep(poll_s)
            state = http.get(f"{base}/audit/{job_id}").json()
            # A finished job stops reporting `done`; falling back to 0 printed
            # a phantom final row counting backwards from ten.
            done = state.get("done", last if last >= 0 else 0)
            if done != last:
                marks.append((time.monotonic() - started, done))
                last = done
            if state.get("status") in {"done", "failed"}:
                state["wall"] = time.monotonic() - started
                return state, marks


def per_line(marks: list[tuple[float, int]]) -> list[tuple[int, float, int]]:
    """Seconds between one completion and the next, and how many landed at once.

    A batch bigger than 1 is the pool working: four lines finishing inside one
    poll interval means four were in flight. Sequential execution produces a
    flat run of single completions, evenly spaced.
    """
    rows = []
    previous_t, previous_done = 0.0, 0
    for at, done in marks:
        rows.append((done, at - previous_t, done - previous_done))
        previous_t, previous_done = at, done
    return rows


def attempts(trace: list[dict]) -> list[tuple[str, int]]:
    """One row per line, from the loop's own summary node.

    A line with more than one attempt was judged, found wanting, had its query
    rewritten and was retrieved again - so it paid for retrieval twice or
    three times, which is the expensive half.
    """
    return [
        (
            str(step.get("item", "?")),
            int(step.get("attempts", 1)),
            str(step.get("backend", "?")),
        )
        for step in trace
        if step.get("node") == "summary"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--bill", default="B01")
    parser.add_argument("--poll", type=float, default=0.2)
    args = parser.parse_args()

    payload = load_bill(args.bill)
    print(f"{args.bill}: policy={payload['policy']} sum_insured={payload['sum_insured']:,.0f}")

    state, marks = run(args.base, payload, args.poll)
    if state.get("status") == "failed":
        print(f"FAILED: {state.get('error')}")
        return 1

    report = state.get("report") or {}
    lines = report.get("lines", [])
    wall = state["wall"]

    print()
    print(f"{'wall clock':<24}{wall:>8.1f}s   {len(lines)} lines")
    print(f"{'seconds per line':<24}{wall / max(1, len(lines)):>8.1f}s")
    print()
    print(f"{'line':>5}  {'gap':>7}  {'landed together':>16}")
    for done, gap, batch in per_line(marks):
        flag = "  <- concurrent" if batch > 1 else ""
        print(f"{done:>5}  {gap:>6.1f}s  {batch:>16}{flag}")

    biggest = max((batch for _, _, batch in per_line(marks)), default=1)
    print()
    print(f"most lines finishing at once: {biggest}{'  (sequential)' if biggest == 1 else ''}")

    rows = attempts(report.get("trace", []))
    if rows:
        print()
        # "none" means the line never reached the model: a non-payable item or
        # a room-rent table lookup, both of which are free.
        used = {}
        for _, _, backend in rows:
            used[backend] = used.get(backend, 0) + 1
        print(
            "backend that actually judged each line: "
            + ", ".join(f"{n} x {name}" for name, n in sorted(used.items()))
        )

        retried = [(item, n) for item, n, _ in rows if n > 1]
        print(
            f"lines that retried: {len(retried)} of {len(rows)}"
            "   (a retry pays for retrieval again)"
        )
        for item, n in retried:
            print(f"   {n} attempts  {item}")

    fallback = [s for s in report.get("trace", []) if "fallback" in json.dumps(s).lower()]
    if fallback:
        print()
        print("BACKEND FELL BACK MID-RUN:")
        for step in fallback:
            print(f"   {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
