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
