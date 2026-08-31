"""Logging setup, plus the JSONL trace writer the agent and UI both read.

Two separate concerns on purpose:

* `setup_logging()` configures human-readable console logging for developers.
* `TraceWriter` appends one JSON object per agent step to a `.jsonl` file, so
  Phase 6 can replay a run and the frontend can show "why did it decide that".
"""

import json
import logging
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import settings

_CONFIGURED = False


def setup_logging(level: str | None = None, *, force: bool = False) -> None:
    """Configure root logging once. Safe to call from any entry point."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(name)-22s %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel((level or settings.log_level).upper())

    # These are chatty and drown out anything useful.
    for noisy in ("httpx", "httpcore", "urllib3", "chromadb", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class TraceWriter:
    """Append-only JSONL trace, one record per agent step.

    Also keeps the records in memory so `AuditReport.trace` can carry them
    back to the API without re-reading the file.
    """

    def __init__(self, run_id: str, path: Path | None = None) -> None:
        self.run_id = run_id
        self.path = path or (settings.traces_dir / f"{run_id}.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._started = time.perf_counter()

    def step(self, node: str, **fields: Any) -> dict[str, Any]:
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "ts": _utc_now(),
            "elapsed_s": round(time.perf_counter() - self._started, 3),
            "node": node,
            **fields,
        }
        with self._lock:
            self.records.append(record)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
