"""gateway: the only service the browser talks to.

It owns the public shape of the API - the same one the monolith in `api/`
serves - and forwards the work. It parses the multipart form, masks the bill
before it leaves the process, and routes: audits and comparisons to
audit-service, policy uploads to ingestion-service.

The three inner services are not published to the host in
`docker-compose.yml`; this is the way in.
"""

from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api.shared import build_schedule, check_policy, masked_bill, policy_rows
from core import llm
from core.config import settings
from core.logging_conf import get_logger, setup_logging
from services.common import client, probe

log = get_logger(__name__)
setup_logging()
# Somebody is waiting on the other end of this, so the hosted model is
# the default here. BA_LLM_BACKEND overrides it, which is how docker
# and k8s choose without a code change.
llm.use_backend(settings.backend_for("api"))

app = FastAPI(
    title="Bill Auditor gateway",
    version="0.1.0",
    description=(
        "The public API. Audits take 30-60 seconds, so POST /audit returns a "
        "job id and the client polls GET /audit/{job_id}."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIT = settings.audit_url.rstrip("/")
INGESTION = settings.ingestion_url.rstrip("/")


def forward(method: str, url: str, **kwargs: Any) -> Any:
    """One hop to an inner service, with its error passed through honestly."""
    try:
        with client() as http:
            response = http.request(method, url, **kwargs)
    except Exception as exc:
        raise HTTPException(502, f"{url} did not answer: {exc}") from exc
    if response.status_code >= 400:
        detail = response.json().get("detail") if response.content else response.text
        raise HTTPException(response.status_code, detail or response.text)
    return response.json()


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    """One call that says what is up and what is not.

    The gateway is useless without audit-service, so its own status follows
    its dependencies rather than reporting a cheerful ok while nothing works.
    """
    dependencies = [
        probe("audit-service", settings.audit_url),
        probe("ingestion-service", settings.ingestion_url),
    ]
    if settings.retrieval_url:
        dependencies.append(probe("retrieval-service", settings.retrieval_url))
    healthy = all(dep["status"] == "ok" for dep in dependencies)
    return {"status": "ok" if healthy else "degraded", "dependencies": dependencies}


@app.get("/policies", tags=["meta"])
def policies() -> list[dict[str, Any]]:
    """Served here rather than forwarded: it is a read of the shared index."""
    return policy_rows()


def audit_body(
    bill_text: str | None,
    bill: UploadFile | None,
    sum_insured: float,
    policy: str | None,
    policy_start_date: str | None,
    admission_date: str | None,
    room_limit_per_day: float | None,
    room_category: str | None,
    differential_billing: bool,
) -> dict[str, Any]:
    schedule = build_schedule(room_limit_per_day, room_category)
    return {
        # Masked here, at the edge, before it crosses a network boundary.
        "bill_text": masked_bill(bill_text, bill),
        "policy": policy,
        "sum_insured": sum_insured,
        "policy_start_date": policy_start_date,
        "admission_date": admission_date,
        "room_limit_per_day": schedule.room_limit_per_day if schedule else None,
        "room_category": schedule.room_category if schedule else None,
        "differential_billing": differential_billing,
    }


@app.post("/audit", status_code=202, tags=["audit"])
def create_audit(
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
    check_policy(policy)
    body = audit_body(
        bill_text,
        bill,
        sum_insured,
        policy,
        policy_start_date,
        admission_date,
        room_limit_per_day,
        room_category,
        differential_billing,
    )
    return forward("POST", f"{AUDIT}/audit", json=body)


@app.post("/compare", status_code=202, tags=["audit"])
def create_compare(
    sum_insured: Annotated[float, Form(gt=0)],
    bill_text: Annotated[str | None, Form()] = None,
    bill: Annotated[UploadFile | None, File()] = None,
    policy_start_date: Annotated[str | None, Form()] = None,
    admission_date: Annotated[str | None, Form()] = None,
    room_limit_per_day: Annotated[float | None, Form()] = None,
    room_category: Annotated[str | None, Form()] = None,
    differential_billing: Annotated[bool, Form()] = True,
) -> dict[str, str]:
    body = audit_body(
        bill_text,
        bill,
        sum_insured,
        None,
        policy_start_date,
        admission_date,
        room_limit_per_day,
        room_category,
        differential_billing,
    )
    return forward("POST", f"{AUDIT}/compare", json=body)


@app.get("/audit/{job_id}", tags=["audit"])
def audit_status(job_id: str) -> dict[str, Any]:
    return forward("GET", f"{AUDIT}/audit/{job_id}")


@app.get("/compare/{job_id}", tags=["audit"])
def compare_status(job_id: str) -> dict[str, Any]:
    return forward("GET", f"{AUDIT}/compare/{job_id}")


@app.post("/policies/upload", status_code=202, tags=["policies"])
def upload_policy(
    file: Annotated[UploadFile, File()], background: BackgroundTasks
) -> dict[str, str]:
    """Streamed on to ingestion-service, which owns the index."""
    del background  # the work happens in ingestion-service, not here
    content = file.file.read()
    return forward(
        "POST",
        f"{INGESTION}/policies/upload",
        files={"file": (file.filename or "policy.pdf", content, "application/pdf")},
    )


@app.get("/jobs/{job_id}", tags=["meta"])
def job_status(job_id: str) -> dict[str, Any]:
    """Indexing jobs live in ingestion-service."""
    return forward("GET", f"{INGESTION}/jobs/{job_id}")
