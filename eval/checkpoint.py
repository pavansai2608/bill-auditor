"""Per-bill checkpoints, so a crash at bill 38 does not discard bills 1-37.

A 44-bill run is forty minutes of model calls. On 2026-09-02 one died at B38 -
Ollama stopped answering, three connection-level failures in a row, then the
process exited - and every completed bill went with it. Nothing reached
`eval/results.md`. That is a design defect, not bad luck: the work was done and
then thrown away.

So each bill's result is written the moment it finishes, and a later run picks
up where the last one stopped.

**This is not a shortcut past the model.** A checkpoint stores the exact
`AuditReport` the run produced, and replaying it folds the same numbers into
the same tallies. What makes that safe is the two hashes: the bill's entry and
the answer key entry it was scored against. Change either and the checkpoint is
refused, because a stale checkpoint that still counts is how a score comes to
describe inputs that no longer exist.

The stored fields are everything needed to rebuild the row - per-line verdicts,
citations, payout figures - plus the backend and model that actually answered,
so a row can never silently mix two models.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.models import AuditReport

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "eval" / ".cache" / "runs"

# Bumped when the stored shape changes, so old files are refused rather than
# half-read.
FORMAT = 2


def digest(value: Any) -> str:
    """A stable hash of anything JSON can hold.

    `sort_keys` matters: a dict that round-trips through JSON in a different
    order is the same answer key entry and must not invalidate the run.
    """
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass
class Checkpoint:
    """One finished bill, and the inputs it is only valid for."""

    bill_id: str
    report: AuditReport
    elapsed: float
    tool_calls: int
    backend: str
    model: str
    bill_hash: str
    key_hash: str

    def to_json(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "bill_id": self.bill_id,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "backend": self.backend,
            "model": self.model,
            "bill_hash": self.bill_hash,
            "key_hash": self.key_hash,
            "elapsed": self.elapsed,
            "tool_calls": self.tool_calls,
            "report": self.report.model_dump(),
        }


def run_dir(version: str) -> Path:
    """One directory per version label, so two versions never share results."""
    # A version label reaches the filesystem, and "../" in one would not be
    # funny. Only the characters a label legitimately uses survive.
    safe = "".join(c for c in version if c.isalnum() or c in "._-") or "unlabelled"
    return RUNS_DIR / safe


def path_for(version: str, bill_id: str) -> Path:
    safe = "".join(c for c in bill_id if c.isalnum() or c in "._-")
    return run_dir(version) / f"{safe}.json"


def save(version: str, checkpoint: Checkpoint) -> Path:
    """Write one finished bill, atomically.

    Atomically because the thing being defended against is the process dying:
    a half-written JSON file that loads as a truncated report would be worse
    than no file at all.
    """
    target = path_for(version, checkpoint.bill_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(checkpoint.to_json(), indent=1), encoding="utf-8")
    tmp.replace(target)
    return target


def load(version: str, bill_id: str, *, bill_hash: str, key_hash: str) -> Checkpoint | None:
    """A previously finished bill, or None if there is nothing usable.

    Returns None rather than raising for every reason a checkpoint can be
    unusable - absent, truncated, written by an older format, or belonging to
    inputs that have since changed. The caller re-runs the bill, which is
    always correct and only ever costs time.
    """
    target = path_for(version, bill_id)
    if not target.exists():
        return None

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None

    if raw.get("format") != FORMAT:
        return None
    # The whole point of the file. A checkpoint scored against a different bill
    # or a different answer is not a saving, it is a wrong number.
    if raw.get("bill_hash") != bill_hash or raw.get("key_hash") != key_hash:
        return None

    try:
        report = AuditReport.model_validate(raw["report"])
    except Exception:
        return None

    return Checkpoint(
        bill_id=bill_id,
        report=report,
        elapsed=float(raw.get("elapsed", 0.0)),
        tool_calls=int(raw.get("tool_calls", 0)),
        backend=str(raw.get("backend", "")),
        model=str(raw.get("model", "")),
        bill_hash=bill_hash,
        key_hash=key_hash,
    )


def clear(version: str) -> int:
    """Drop every checkpoint for a version. Returns how many were removed."""
    directory = run_dir(version)
    if not directory.exists():
        return 0
    removed = 0
    for path in directory.glob("*.json"):
        path.unlink()
        removed += 1
    return removed
