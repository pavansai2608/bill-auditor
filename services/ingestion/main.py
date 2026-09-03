"""ingestion-service: PDFs in, clauses and embeddings out.

Heavy but rare. Splitting the three policy PDFs and embedding 402 clauses takes
minutes and a lot of memory; it happens when a policy is added, not when a bill
is audited. That difference is the whole reason it is a separate container -
nothing else has to be sized for it.
"""

import re
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from api.jobs import jobs
from api.shared import PDF_MAGIC, SLUG_RE, policy_rows
from core import llm
from core.config import settings
from core.logging_conf import get_logger, setup_logging
from services.common import clause_index_health, start_warm_up, warm_state

log = get_logger(__name__)
setup_logging()
# Somebody is waiting on the other end of this, so the hosted model is
# the default here. BA_LLM_BACKEND overrides it, which is how docker
# and k8s choose without a code change.
llm.use_backend(settings.backend_for("api"))

app = FastAPI(title="ingestion-service", version="0.1.0")


# Load the models now rather than on the first request; see
# services/common.warm_up. /ready reports when that is done.
start_warm_up(reranker=False)


def run_index(job_id: str, policy: str | None) -> None:
    from core import ingest

    try:
        jobs.start(job_id, total=1)
        clauses = ingest.run(force=True)
        if policy is not None and not any(c.policy == policy for c in clauses):
            jobs.fail(job_id, f"no clauses were extracted from {policy!r}")
            return
        jobs.finish(
            job_id,
            {
                "policy": policy,
                "clauses": sum(1 for c in clauses if policy is None or c.policy == policy),
                "total_clauses": len(clauses),
            },
        )
    except Exception as exc:
        jobs.fail(job_id, f"{type(exc).__name__}: {exc}")


@app.get("/health")
def health() -> dict[str, Any]:
    return clause_index_health()


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness, as distinct from liveness.

    /health says the process is alive. This says it can serve a request without
    making the caller wait for a model to load. Kubernetes points its readiness
    probe here so traffic is not routed to a pod that is still warming.
    """
    state = warm_state()
    body = {"ready": state["ready"], "warm_seconds": state["seconds"]}
    if state["error"]:
        body["error"] = state["error"]
    return JSONResponse(body, status_code=200 if state["ready"] else 503)


@app.get("/policies")
def policies() -> list[dict[str, Any]]:
    return policy_rows()


@app.post("/policies/upload", status_code=202)
def upload_policy(
    background: BackgroundTasks, file: Annotated[UploadFile, File()]
) -> dict[str, str]:
    """Store a policy PDF and index it. Poll `GET /jobs/{job_id}`."""
    name = (file.filename or "").strip()
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "upload a .pdf")

    raw = file.file.read()
    if not raw.startswith(PDF_MAGIC):
        raise HTTPException(400, "that file is not a PDF")
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"the PDF is larger than {settings.max_upload_mb} MB")

    # Rebuilt from scratch, never taken from the upload, so nothing can be
    # written outside the policies directory.
    policy = SLUG_RE.sub("_", re.sub(r"\.pdf$", "", name, flags=re.I).lower()).strip("_")
    if not policy:
        raise HTTPException(400, "the filename has no usable characters")

    settings.ensure_dirs()
    (settings.policies_dir / f"{policy}.pdf").write_bytes(raw)
    log.info("stored %s (%d bytes) as %s.pdf", name, len(raw), policy)

    job = jobs.create("index", total=1)
    background.add_task(run_index, job.job_id, policy)
    return {"job_id": job.job_id, "policy": policy}


@app.post("/reindex", status_code=202)
def reindex(background: BackgroundTasks) -> dict[str, str]:
    """Re-split and re-embed everything in data/policies."""
    job = jobs.create("index", total=1)
    background.add_task(run_index, job.job_id, None)
    return {"job_id": job.job_id}


@app.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id!r}")
    return {"kind": job.kind, **job.as_status()}
