"""Bits every service needs: a health payload and one HTTP client.

Nothing here knows an audit rule. The rules live in `core/`, which every
service imports rather than reimplements — that is the whole reason the split
is safe to do at all.
"""

from typing import Any

import httpx

from core.config import settings
from core.ingest import load_clauses
from core.logging_conf import get_logger

log = get_logger(__name__)


def client() -> httpx.Client:
    """One place for the timeout. An audit is slow, so this is not the default."""
    return httpx.Client(timeout=settings.service_timeout_s)


def clause_index_health() -> dict[str, Any]:
    """Every service that reads clauses reports the same thing about them."""
    try:
        clauses = load_clauses()
    except Exception as exc:  # health answers, it never raises
        return {"status": "degraded", "error": str(exc), "clauses": 0}
    return {"status": "ok", "clauses": len(clauses)}


def probe(name: str, url: str) -> dict[str, Any]:
    """Ask a dependency how it is. Used by the gateway to answer for everyone."""
    try:
        with httpx.Client(timeout=5) as http:
            response = http.get(f"{url.rstrip('/')}/health")
            body = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            return {
                "service": name,
                "url": url,
                "status": body.get("status", "unknown"),
                **{k: v for k, v in body.items() if k not in {"status", "dependencies"}},
            }
    except Exception as exc:
        return {"service": name, "url": url, "status": "unreachable", "error": str(exc)[:120]}


# --------------------------------------------------------------------------
# warm-up
# --------------------------------------------------------------------------

_warm = {"ready": False, "error": "", "seconds": 0.0}


def warm_state() -> dict[str, Any]:
    return dict(_warm)


def warm_up(*, reranker: bool) -> None:
    """Load the models now, so the first request does not pay for them.

    Measured cold on a laptop: 44-74s to load bge-base and, where needed, the
    bge-reranker cross-encoder. Without this the first person to reach a freshly
    deployed pod waits a minute for something that has nothing to do with their
    bill - and in Kubernetes it is worse, because the readiness probe passes the
    moment uvicorn binds and traffic is routed to a pod that is still warming.

    Ingestion embeds but never reranks, so it skips the cross-encoder.
    """
    import time

    started = time.monotonic()
    try:
        from core.embeddings import get_embeddings

        get_embeddings().embed_query("warm up")
        if reranker:
            from core.retrieve import get_cross_encoder

            get_cross_encoder().score([("warm up", "warm up")])
        _warm["ready"] = True
    except Exception as exc:  # a failed warm-up must be visible, not silent
        _warm["error"] = f"{type(exc).__name__}: {exc}"
        log.exception("warm-up failed")
    finally:
        _warm["seconds"] = round(time.monotonic() - started, 1)
        if _warm["ready"]:
            log.info("models warm in %.1fs", _warm["seconds"])


def start_warm_up(*, reranker: bool) -> None:
    """Warm in a background thread.

    Not in the lifespan's critical path: a synchronous load would hold the
    event loop for a minute, which makes the liveness probe time out and
    Kubernetes restart the pod it is waiting for.
    """
    import threading

    threading.Thread(target=warm_up, kwargs={"reranker": reranker}, daemon=True).start()
