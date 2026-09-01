"""Make `core` reach retrieval over HTTP instead of doing it in-process.

`core.agent` and `core.audit` both import `search` into their own namespace, so
pointing them at the service is a matter of replacing that one name in each.
Nothing else about the agent changes, and the audit rules stay in `core/` where
they are tested.

When `BA_RETRIEVAL_URL` is empty the patch is skipped and everything runs in
one process, which is how the monolith and the eval work.
"""

from core.config import settings
from core.logging_conf import get_logger
from core.models import Clause
from core.retrieve import RetrievedClause
from services.common import client

log = get_logger(__name__)


def remote_search(
    query: str, policy: str, *, top_n: int | None = None, follow_refs: bool = True
) -> list[RetrievedClause]:
    """Same signature as `core.retrieve.search`, same return type."""
    with client() as http:
        response = http.post(
            f"{settings.retrieval_url.rstrip('/')}/search",
            json={"query": query, "policy": policy, "top_n": top_n, "follow_refs": follow_refs},
        )
        response.raise_for_status()
        payload = response.json()

    return [
        RetrievedClause(
            clause=Clause(**row["clause"]),
            score=row["score"],
            matched_text=row["matched_text"],
            via_ref_of=row.get("via_ref_of"),
        )
        for row in payload["results"]
    ]


def install() -> bool:
    """Point the agent and the naive path at the service. Returns whether it did."""
    if not settings.retrieval_url:
        log.info("BA_RETRIEVAL_URL is empty, so retrieval stays in this process")
        return False

    import core.agent as agent
    import core.audit as audit

    agent.search = remote_search
    audit.search = remote_search
    log.info("retrieval now goes to %s", settings.retrieval_url)
    return True
