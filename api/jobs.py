"""In-memory job store. No database, by design.

An audit takes 30-60 seconds, which is far too long to hold a request open, so
`POST /audit` starts the work and hands back a job id to poll. The store is a
dict behind a lock: FastAPI runs a synchronous background task in a worker
thread, so two jobs really can touch this at the same time.

Jobs do not survive a restart. That is the deliberate trade - the alternative
is a database, and this system has no state worth persisting: an audit is
cheap to re-run and every model call is already cached to disk.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from core.config import settings
from core.logging_conf import get_logger

log = get_logger(__name__)

JobStatus = Literal["queued", "running", "done", "failed"]
JobKind = Literal["audit", "compare", "index"]


@dataclass
class Job:
    job_id: str
    kind: JobKind
    status: JobStatus = "queued"
    done: int = 0
    total: int = 0
    report: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None

    def as_status(self) -> dict[str, Any]:
        """What the poll endpoint returns, shaped by where the job has got to."""
        if self.status == "done":
            return {"job_id": self.job_id, "status": "done", "report": self.report}
        if self.status == "failed":
            return {"job_id": self.job_id, "status": "failed", "error": self.error}
        return {
            "job_id": self.job_id,
            "status": self.status,
            "done": self.done,
            "total": self.total,
        }


class JobStore:
    """Every mutation takes the lock. Reads copy, so a caller cannot mutate."""

    def __init__(self, keep: int | None = None):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._keep = keep or settings.max_jobs_kept

    def create(self, kind: JobKind, total: int = 0) -> Job:
        job = Job(job_id=uuid.uuid4().hex[:12], kind=kind, total=total)
        with self._lock:
            self._jobs[job.job_id] = job
            # Oldest first, so trimming drops the ones least likely to be polled.
            while len(self._jobs) > self._keep:
                self._jobs.pop(next(iter(self._jobs)))
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start(self, job_id: str, total: int = 0) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "running"
                if total:
                    job.total = total

    def set_total(self, job_id: str, total: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.total = total

    def progress(self, job_id: str, done: int, total: int | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.done = done
                if total is not None:
                    job.total = total

    def finish(self, job_id: str, report: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"
                job.report = report
                job.done = job.total
                job.finished_at = datetime.now(UTC).isoformat()

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error = error
                job.finished_at = datetime.now(UTC).isoformat()
        log.warning("job %s failed: %s", job_id, error)


jobs = JobStore()
