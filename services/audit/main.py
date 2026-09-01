"""audit-service: the agent loop, the second pass and the guardrails.

Slow and CPU-bound. One request occupies a worker for the better part of a
minute, which is why it is its own container and why it is the one with the
largest resource limits in `k8s/`.

It does not do its own retrieval: `remote_retrieval.install()` points
`core.agent.search` at retrieval-service. The audit rules themselves are the
same `core/` code the tests exercise.
"""

from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from api.jobs import Job, jobs
from api.shared import known_policies, report_payload
from core.assumptions import Assumptions
from core.audit import audit_lines
from core.config import settings
from core.logging_conf import get_logger, setup_logging
from core.models import AuditReport, PolicySchedule
from services.audit import remote_retrieval
from services.common import clause_index_health, probe

log = get_logger(__name__)
setup_logging()

app = FastAPI(title="audit-service", version="0.1.0")
REMOTE_RETRIEVAL = remote_retrieval.install()


class AuditRequest(BaseModel):
    """The bill arrives already masked: the gateway strips identifiers."""

    bill_text: str
    policy: str | None = None
    sum_insured: float = Field(gt=0)
    policy_start_date: str | None = None
    admission_date: str | None = None
    room_limit_per_day: float | None = None
    room_category: str | None = None
    differential_billing: bool = True

    def schedule(self) -> PolicySchedule | None:
        if self.room_limit_per_day is None and not self.room_category:
            return None
        return PolicySchedule(
            room_limit_per_day=self.room_limit_per_day, room_category=self.room_category
        )


def run_one(job_id: str, request: AuditRequest, policy: str) -> AuditReport:
    from core.bill import parse_bill

    lines = parse_bill(request.bill_text)
    jobs.progress(job_id, 0, len(lines))
    return audit_lines(
        lines,
        policy,
        request.sum_insured,
        request.schedule(),
        Assumptions(differential_billing=request.differential_billing),
        use_agent=True,
        second_pass=True,
        policy_start_date=request.policy_start_date,
        admission_date=request.admission_date,
        on_progress=lambda done, total: jobs.progress(job_id, done, total),
    )


def run_audit(job_id: str, request: AuditRequest) -> None:
    try:
        jobs.start(job_id)
        report = run_one(job_id, request, request.policy or known_policies()[0])
        jobs.finish(job_id, report_payload(report))
    except Exception as exc:  # the job records it rather than raising
        jobs.fail(job_id, f"{type(exc).__name__}: {exc}")


def run_compare(job_id: str, request: AuditRequest) -> None:
    from core.bill import parse_bill

    try:
        jobs.start(job_id)
        policies = known_policies()
        lines = parse_bill(request.bill_text)
        jobs.progress(job_id, 0, len(lines) * len(policies))

        reports: list[AuditReport] = []
        finished = 0
        for policy in policies:
            reports.append(
                audit_lines(
                    lines,
                    policy,
                    request.sum_insured,
                    request.schedule(),
                    Assumptions(differential_billing=request.differential_billing),
                    use_agent=True,
                    second_pass=True,
                    policy_start_date=request.policy_start_date,
                    admission_date=request.admission_date,
                    on_progress=lambda done, _total, base=finished: jobs.progress(
                        job_id, base + done
                    ),
                )
            )
            finished += len(lines)

        best = max(reports, key=lambda r: r.total_allowed)
        worst = min(reports, key=lambda r: r.total_allowed)
        jobs.finish(
            job_id,
            {
                "reports": [report_payload(r) for r in reports],
                "best_policy": best.policy,
                "difference": round(best.total_allowed - worst.total_allowed, 2),
            },
        )
    except Exception as exc:
        jobs.fail(job_id, f"{type(exc).__name__}: {exc}")


@app.get("/health")
def health() -> dict[str, Any]:
    body = clause_index_health()
    body["remote_retrieval"] = REMOTE_RETRIEVAL
    if REMOTE_RETRIEVAL:
        body["retrieval"] = probe("retrieval-service", settings.retrieval_url)["status"]
    body["model"] = settings.ollama_model
    return body


@app.post("/audit", status_code=202)
def create_audit(request: AuditRequest, background: BackgroundTasks) -> dict[str, str]:
    if request.policy not in known_policies():
        raise HTTPException(404, f"unknown policy {request.policy!r}")
    job = jobs.create("audit")
    background.add_task(run_audit, job.job_id, request)
    return {"job_id": job.job_id}


@app.post("/compare", status_code=202)
def create_compare(request: AuditRequest, background: BackgroundTasks) -> dict[str, str]:
    job = jobs.create("compare")
    background.add_task(run_compare, job.job_id, request)
    return {"job_id": job.job_id}


def fetch(job_id: str, kind: str) -> Job:
    job = jobs.get(job_id)
    if job is None or job.kind != kind:
        raise HTTPException(404, f"no {kind} job {job_id!r}")
    return job


@app.get("/audit/{job_id}")
def audit_status(job_id: Annotated[str, "job id"]) -> dict[str, Any]:
    return fetch(job_id, "audit").as_status()


@app.get("/compare/{job_id}")
def compare_status(job_id: str) -> dict[str, Any]:
    return fetch(job_id, "compare").as_status()
