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
the same tallies. What makes that safe is three things: the bill's entry, the
answer key entry it was scored against, and a fingerprint of the code that
produced it. Change any of them and the checkpoint is refused, because a stale
checkpoint that still counts is how a score comes to describe inputs - or a
system - that no longer exists.

The fingerprint was added after a Jenkins build finished the Eval stage in one
second on a warm workspace. Only the inputs were hashed, so a commit that
damaged the auditor replayed the previous run's reports and the accuracy gate
passed. That is the gate failing at precisely the job it exists to do.

The stored fields are everything needed to rebuild the row - per-line verdicts,
citations, payout figures - plus the backend and model that actually answered,
so a row can never silently mix two models.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.models import AuditReport

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "eval" / ".cache" / "runs"

# Bumped when the stored shape changes, so old files are refused rather than
# half-read. 3 added the code fingerprint.
FORMAT = 3

# What the fingerprint covers, and why this boundary.
#
# **All of `core/`.** That directory *is* the audit path - it is defined by the
# project as the audit rules, and it imports no web framework precisely so that
# it can be. A curated list of "the modules that matter" was the obvious
# alternative and is the wrong answer: the first time someone adds a module and
# forgets to list it, stale results leak through silently, which is the same
# class of bug this exists to close. Hashing the directory cannot forget.
#
# **The clause index.** Re-ingesting changes what retrieval returns, so it
# changes results, and until now it invalidated nothing at all.
#
# The cost is that a comment-only edit inside `core/` throws away a warm run.
# That is the safe direction to be wrong in: it costs time, where the reverse
# costs a wrong number in `results.md`. `--fresh` exists for the other case.
AUDIT_SOURCE_DIR = ROOT / "core"
INDEX_FILES = (ROOT / "data" / "clauses.json", ROOT / "data" / "non_payable.json")


def digest(value: Any) -> str:
    """A stable hash of anything JSON can hold.

    `sort_keys` matters: a dict that round-trips through JSON in a different
    order is the same answer key entry and must not invalidate the run.
    """
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def code_digest() -> str:
    """A hash of every source file that can change an audit result.

    Cached for the process: the files cannot change under a running eval, and
    hashing 20-odd modules per bill would be waste. Paths are relative and
    sorted, so the digest does not depend on where the repository sits or on
    the order the filesystem hands them back.
    """
    parts: list[tuple[str, str]] = []
    for path in sorted(AUDIT_SOURCE_DIR.rglob("*.py")):
        parts.append((str(path.relative_to(ROOT)), _file_digest(path)))
    for path in INDEX_FILES:
        if path.exists():
            parts.append((str(path.relative_to(ROOT)), _file_digest(path)))
    return digest(parts)


def tuning_digest() -> str:
    """The settings that change a result without changing a line of source.

    `core.retrieve` already keeps this list, because its own disk cache has the
    same problem one level down: two runs at different `rerank_top_n` values ask
    the same question and must not share an answer. Reusing it means the two
    caches cannot drift apart about what "the same run" means.

    This exists because the code digest above cannot see a setting.
    `BA_RERANK_TOP_N=8 uv run python eval/evaluate.py --version v9` would have
    replayed v9's stored reports and reported v9's numbers as though they were
    the experiment's - the same failure the code fingerprint was added to close,
    wearing an environment variable instead of a commit.
    """
    from core.retrieve import _config_fingerprint

    return digest(_config_fingerprint())


def fingerprint(*, use_agent: bool, second_pass: bool) -> str:
    """The code, the tuning and the switches that together decide what a bill scores.

    The two flags belong here as much as the source does. `--second-pass`
    changes every associated line on a bill that breached its room limit, and
    before this it changed nothing about the checkpoint key - so a run with the
    flag happily replayed reports produced without it.
    """
    return digest(
        {
            "code": code_digest(),
            "tuning": tuning_digest(),
            "agent": use_agent,
            "second_pass": second_pass,
        }
    )


@dataclass
class Checkpoint:
    """One finished bill, and the inputs and code it is only valid for."""

    bill_id: str
    report: AuditReport
    elapsed: float
    tool_calls: int
    backend: str
    model: str
    bill_hash: str
    key_hash: str
    fingerprint: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "bill_id": self.bill_id,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "backend": self.backend,
            "model": self.model,
            "bill_hash": self.bill_hash,
            "key_hash": self.key_hash,
            # Recorded, not only compared. A stored result should say which code
            # produced it, for the same reason the row records the backend.
            "fingerprint": self.fingerprint,
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


def path_for(version: str, bill_id: str, fingerprint: str = "") -> Path:
    """Where one bill's result lives, scoped to the code that produced it.

    The fingerprint is in the *file name*, not just inside the file, so results
    from different builds sit side by side instead of overwriting each other.
    That is what makes reverting a bad commit free: the checkpoints from before
    the break are still on disk and still match, so the green build after a
    revert replays them. Only the damaged build pays for a recompute - which is
    the right way round for the incentive to point.
    """
    safe = "".join(c for c in bill_id if c.isalnum() or c in "._-")
    if fingerprint:
        return run_dir(version) / f"{safe}.{fingerprint[:12]}.json"
    return run_dir(version) / f"{safe}.json"


def save(version: str, checkpoint: Checkpoint) -> Path:
    """Write one finished bill, atomically.

    Atomically because the thing being defended against is the process dying:
    a half-written JSON file that loads as a truncated report would be worse
    than no file at all.
    """
    target = path_for(version, checkpoint.bill_id, checkpoint.fingerprint)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(checkpoint.to_json(), indent=1), encoding="utf-8")
    tmp.replace(target)
    return target


def load(
    version: str,
    bill_id: str,
    *,
    bill_hash: str,
    key_hash: str,
    fingerprint: str,
) -> Checkpoint | None:
    """A previously finished bill, or None if there is nothing usable.

    Returns None rather than raising for every reason a checkpoint can be
    unusable - absent, truncated, written by an older format, or belonging to
    inputs that have since changed. The caller re-runs the bill, which is
    always correct and only ever costs time.
    """
    target = path_for(version, bill_id, fingerprint)
    if not target.exists():
        # A checkpoint written before results were scoped by fingerprint.
        # Fall back to the unscoped name so an existing cache is not thrown
        # away wholesale; the fingerprint inside it is still checked below.
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
    # The audit code changed, so the stored report describes a system that no
    # longer exists. Replaying it would let a damaging commit through the gate.
    if raw.get("fingerprint") != fingerprint:
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
        fingerprint=fingerprint,
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
