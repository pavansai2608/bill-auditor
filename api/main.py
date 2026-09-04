"""FastAPI over the audit. `core/` knows nothing about this file.

An audit is 30-60 seconds of model calls, so no endpoint waits for one:
`POST /audit` starts a background task and returns a job id, and the client
polls `GET /audit/{job_id}` for `done`/`total` until a report appears.

The report carries its trace and its assumptions, not just the numbers. A
deduction the user cannot trace back to a clause is exactly what this project
exists to replace, and an assumption the system made silently would be the
same failure wearing a different hat.
"""

from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api.jobs import Job, jobs
from api.shared import (
    PDF_MAGIC,
    SLUG_RE,
    build_schedule,
    check_policy,
    known_policies,
    masked_bill,
    policy_rows,
    report_payload,
)
from core import llm, retrieve
from core.assumptions import Assumptions
from core.audit import audit_lines
from core.config import settings
from core.ingest import load_clauses
from core.logging_conf import get_logger, setup_logging
from core.models import AuditReport

log = get_logger(__name__)
setup_logging()
# Somebody is waiting on the other end of this, so the hosted model is
# the default here. BA_LLM_BACKEND overrides it, which is how docker
# and k8s choose without a code change.
llm.use_backend(settings.backend_for("api"))

app = FastAPI(
    title="Bill Auditor",
    version="0.1.0",
    description=(
        "Audits an Indian health insurance claim bill against the policy that "
        "governs it. Every deduction cites the clause that caused it; a line "
        "with no clearly applicable clause is flagged rather than guessed at."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# background work
# --------------------------------------------------------------------------


def run_audit(job_id: str, bill_text: str, policy: str, options: dict[str, Any]) -> None:
    """One bill against one policy. Runs in a worker thread, never in a request."""
    from core.bill import parse_bill

    try:
        jobs.start(job_id)
        lines = parse_bill(bill_text)
        jobs.progress(job_id, 0, len(lines))
        report = audit_lines(
            lines,
            policy,
            options["sum_insured"],
            options["schedule"],
            Assumptions(differential_billing=options["differential_billing"]),
            use_agent=True,
            second_pass=True,
            policy_start_date=options["policy_start_date"],
            admission_date=options["admission_date"],
            on_progress=lambda done, total: jobs.progress(job_id, done, total),
        )
        jobs.finish(job_id, report_payload(report))
    except Exception as exc:  # the job records the failure rather than raising
        jobs.fail(job_id, f"{type(exc).__name__}: {exc}")


def run_compare(job_id: str, bill_text: str, options: dict[str, Any]) -> None:
    """The same bill against every indexed policy, to see which pays most."""
    from core.bill import parse_bill

    try:
        jobs.start(job_id)
        policies = known_policies()
        lines = parse_bill(bill_text)
        jobs.progress(job_id, 0, len(lines) * len(policies))

        reports: list[AuditReport] = []
        finished = 0
        for policy in policies:
            report = audit_lines(
                lines,
                policy,
                options["sum_insured"],
                options["schedule"],
                Assumptions(differential_billing=options["differential_billing"]),
                use_agent=True,
                second_pass=True,
                policy_start_date=options["policy_start_date"],
                admission_date=options["admission_date"],
                on_progress=lambda done, _total, base=finished: jobs.progress(job_id, base + done),
            )
            reports.append(report)
            finished += len(lines)

        best = max(reports, key=lambda r: r.total_allowed)
        worst = min(reports, key=lambda r: r.total_allowed)
        jobs.finish(
            job_id,
            {
                "reports": [report_payload(r) for r in reports],
                "best_policy": best.policy,
                # The spread across policies: what the choice of insurer is
                # worth on this bill.
                "difference": round(best.total_allowed - worst.total_allowed, 2),
            },
        )
    except Exception as exc:  # any failure belongs on the job, not in a traceback
        jobs.fail(job_id, f"{type(exc).__name__}: {exc}")


def run_index(job_id: str, policy: str) -> None:
    """Re-split and re-index every policy PDF, including the new one."""
    from core import ingest

    try:
        jobs.start(job_id, total=1)
        clauses = ingest.run(force=True)
        mine = [c for c in clauses if c.policy == policy]
        if not mine:
            jobs.fail(job_id, f"no clauses were extracted from {policy!r}")
            return
        jobs.finish(
            job_id,
            {"policy": policy, "clauses": len(mine), "total_clauses": len(clauses)},
        )
    except Exception as exc:  # any failure belongs on the job, not in a traceback
        jobs.fail(job_id, f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# endpoints
# --------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    """Is the service up, and is there a clause index behind it?"""
    try:
        clauses = load_clauses()
    except Exception as exc:  # health must answer, not raise
        return {"status": "degraded", "error": str(exc), "clauses": 0}
    backend = llm.active_backend()
    return {
        "status": "ok",
        "clauses": len(clauses),
        "policies": known_policies(),
        # The backend actually in force, and the model that goes with it. This
        # said "qwen3:8b" whatever was running, which is the wrong field to
        # read when an audit is unexpectedly slow.
        "backend": backend,
        "model": settings.groq_model if backend == "groq" else settings.ollama_model,
        # Repeat audits are only fast if these say enabled. Model calls come
        # back from the first, searches from the second; between them they are
        # the whole cost of re-auditing a bill that has been audited before.
        "llm_cache": llm.cache_health(),
        "retrieval_cache": retrieve.cache_health(),
    }


@app.get("/policies", tags=["meta"])
def policies() -> list[dict[str, Any]]:
    """The insurer dropdown."""
    return policy_rows()


@app.post("/audit", status_code=202, tags=["audit"])
def create_audit(
    background: BackgroundTasks,
    policy: Annotated[str, Form()],
    sum_insured: Annotated[float, Form(gt=0)],
    bill_text: Annotated[str | None, Form()] = None,
    bill: Annotated[UploadFile | None, File()] = None,
    policy_start_date: Annotated[str | None, Form()] = None,
    admission_date: Annotated[str | None, Form()] = None,
    room_limit_per_day: Annotated[float | None, Form()] = None,
    room_category: Annotated[str | None, Form()] = None,
    differential_billing: Annotated[bool, Form()] = True,
) -> dict[str, str]:
    """Start an audit. Returns immediately; poll `GET /audit/{job_id}`."""
    check_policy(policy)
    text = masked_bill(bill_text, bill)
    job = jobs.create("audit")
    background.add_task(
        run_audit,
        job.job_id,
        text,
        policy,
        {
            "sum_insured": sum_insured,
            "schedule": build_schedule(room_limit_per_day, room_category),
            "policy_start_date": policy_start_date,
            "admission_date": admission_date,
            "differential_billing": differential_billing,
        },
    )
    return {"job_id": job.job_id}


@app.post("/compare", status_code=202, tags=["audit"])
def create_compare(
    background: BackgroundTasks,
    sum_insured: Annotated[float, Form(gt=0)],
    bill_text: Annotated[str | None, Form()] = None,
    bill: Annotated[UploadFile | None, File()] = None,
    policy_start_date: Annotated[str | None, Form()] = None,
    admission_date: Annotated[str | None, Form()] = None,
    room_limit_per_day: Annotated[float | None, Form()] = None,
    room_category: Annotated[str | None, Form()] = None,
    differential_billing: Annotated[bool, Form()] = True,
) -> dict[str, str]:
    """The same bill against every indexed policy. Poll `GET /compare/{job_id}`."""
    text = masked_bill(bill_text, bill)
    job = jobs.create("compare")
    background.add_task(
        run_compare,
        job.job_id,
        text,
        {
            "sum_insured": sum_insured,
            "schedule": build_schedule(room_limit_per_day, room_category),
            "policy_start_date": policy_start_date,
            "admission_date": admission_date,
            "differential_billing": differential_billing,
        },
    )
    return {"job_id": job.job_id}


def fetch(job_id: str, kind: str) -> Job:
    job = jobs.get(job_id)
    if job is None or job.kind != kind:
        raise HTTPException(404, f"no {kind} job {job_id!r}")
    return job


@app.get("/audit/{job_id}", tags=["audit"])
def audit_status(job_id: str) -> dict[str, Any]:
    """`running` with done/total, or `done` with the report."""
    return fetch(job_id, "audit").as_status()


@app.get("/compare/{job_id}", tags=["audit"])
def compare_status(job_id: str) -> dict[str, Any]:
    return fetch(job_id, "compare").as_status()


@app.post("/policies/upload", status_code=202, tags=["policies"])
def upload_policy(
    background: BackgroundTasks, file: Annotated[UploadFile, File()]
) -> dict[str, str]:
    """Add a policy PDF and index it. Poll `GET /jobs/{job_id}`.

    Indexing re-splits every PDF, which takes a few minutes, so it is a job
    like any other rather than something a request waits for.
    """
    name = (file.filename or "").strip()
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "upload a .pdf")

    raw = file.file.read()
    if not raw.startswith(PDF_MAGIC):
        raise HTTPException(400, "that file is not a PDF")
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"the PDF is larger than {settings.max_upload_mb} MB")

    # Built from scratch, never from the uploaded name, so an upload cannot
    # write outside the policies directory.
    policy = SLUG_RE.sub("_", name[:-4].lower()).strip("_")
    if not policy:
        raise HTTPException(400, "the filename has no usable characters")

    settings.ensure_dirs()
    destination = settings.policies_dir / f"{policy}.pdf"
    destination.write_bytes(raw)
    log.info("stored %s (%d bytes) as %s", name, len(raw), destination)

    job = jobs.create("index", total=1)
    background.add_task(run_index, job.job_id, policy)
    return {"job_id": job.job_id, "policy": policy}


@app.get("/jobs/{job_id}", tags=["meta"])
def job_status(job_id: str) -> dict[str, Any]:
    """Any job, whatever its kind."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id!r}")
    return {"kind": job.kind, **job.as_status()}
