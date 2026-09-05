"""Export one recorded eval run as the example report the static site ships.

The GitHub Pages build has no backend behind it - there is no Ollama, no clause
index and no retriever on a static host - so the report screen there has to be
fed something. The only honest something is a report the system actually
produced, so this lifts one out of `eval/.cache/runs/` and writes it into the
frontend as JSON.

**It never invents a figure.** Every rupee amount, every clause id and every
line of the trace comes from the checkpoint, which is the exact `AuditReport`
that run recorded. What this adds is the `assumptions` block, because that is
what `api/shared.report_payload` adds when the real API answers - the UI reads
it from a field of its own rather than filtering the trace, so a report handed
to the UI by any other route has to carry it too.

The checkpoint directory is gitignored (it is machine-local and derived), so
the output is committed and this script is how it is regenerated:

    uv run python eval/export_example_report.py --run v11-zero-limit-guardrail --bill B01

`tests/test_example_report.py` then holds it to the two things that matter on a
page nobody can re-run: the arithmetic reconciles, and every clause it cites is
a clause that exists in the index.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "eval" / ".cache" / "runs"
OUT = ROOT / "frontend" / "src" / "data" / "exampleReport.json"


def find_checkpoint(run: str, bill: str) -> Path:
    """The checkpoint for one bill in one run, whatever its fingerprint is.

    Files are named `<bill>.<fingerprint>.json`, and older ones have no
    fingerprint at all. Picking the newest keeps this working across both.
    """
    directory = RUNS_DIR / run
    if not directory.is_dir():
        raise SystemExit(f"no such run: {directory}")
    matches = sorted(directory.glob(f"{bill}.*json"), key=lambda p: p.stat().st_mtime)
    if not matches:
        raise SystemExit(f"{directory} holds no checkpoint for {bill}")
    return matches[-1]


def payload(checkpoint: dict[str, Any], run: str) -> dict[str, Any]:
    report = dict(checkpoint["report"])
    # What api/shared.report_payload does, done here for the same reason: the
    # UI reads assumptions from their own field, not out of the trace.
    report["assumptions"] = [e for e in report.get("trace", []) if e.get("assumption")]
    return {
        "recorded": {
            "run": run,
            "bill_id": checkpoint["bill_id"],
            "recorded_at": checkpoint["recorded_at"],
            "backend": checkpoint["backend"],
            "model": checkpoint["model"],
        },
        "report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", default="v11-zero-limit-guardrail", help="a directory under eval/.cache/runs"
    )
    parser.add_argument("--bill", default="B01", help="which bill's report to export")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    path = find_checkpoint(args.run, args.bill)
    checkpoint = json.loads(path.read_text())
    if checkpoint.get("format") != 3:
        raise SystemExit(f"{path} is format {checkpoint.get('format')}, expected 3")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload(checkpoint, args.run), indent=2) + "\n")

    report = checkpoint["report"]
    print(f"{path.relative_to(ROOT)} -> {args.out.relative_to(ROOT)}")
    print(f"  {len(report['lines'])} lines, charged {report['total_charged']:,.0f},")
    print(f"  allowed {report['total_allowed']:,.0f}, {report['flagged_count']} flagged")


if __name__ == "__main__":
    main()
