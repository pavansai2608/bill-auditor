"""retrieval-service: hybrid search and reranking, and nothing else.

Light and frequent. Every audited line calls it at least once, so it holds the
Chroma collection, the BM25 index and the cross-encoder in memory and answers
in milliseconds. It never calls the model and never decides anything.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core import llm
from core.config import settings
from core.logging_conf import get_logger, setup_logging
from core.retrieve import search
from services.common import clause_index_health, start_warm_up, warm_state

log = get_logger(__name__)
setup_logging()
# Somebody is waiting on the other end of this, so the hosted model is
# the default here. BA_LLM_BACKEND overrides it, which is how docker
# and k8s choose without a code change.
llm.use_backend(settings.backend_for("api"))

app = FastAPI(title="retrieval-service", version="0.1.0")


# Load the models now rather than on the first request; see
# services/common.warm_up. /ready reports when that is done.
start_warm_up(reranker=True)


class SearchRequest(BaseModel):
    query: str
    policy: str
    top_n: int | None = Field(default=None, ge=1, le=20)
    follow_refs: bool = True


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


@app.post("/search")
def do_search(request: SearchRequest) -> dict[str, Any]:
    """The same `core.retrieve.search` the monolith calls, over HTTP.

    The response carries the whole clause, not just its id, because the judge
    needs the text and a second lookup would double the traffic for nothing.
    """
    results = search(
        request.query,
        request.policy,
        top_n=request.top_n,
        follow_refs=request.follow_refs,
    )
    return {
        "results": [
            {
                "clause": result.clause.model_dump(),
                "score": result.score,
                "matched_text": result.matched_text,
                "via_ref_of": result.via_ref_of,
            }
            for result in results
        ]
    }
