"""Request shaping shared by the monolith API and the gateway service.

Both take the same multipart form, both have to mask the bill before anything
stores it, and both return the same report shape. Keeping these here means the
gateway is a router rather than a second implementation of the rules.
"""

import re
from typing import Any

from fastapi import HTTPException, UploadFile

from core.config import settings
from core.ingest import load_clauses
from core.masking import mask_pii
from core.models import AuditReport, PolicySchedule
from core.room_limit import sum_insured_options

PDF_MAGIC = b"%PDF"
SLUG_RE = re.compile(r"[^a-z0-9]+")


def known_policies() -> list[str]:
    return sorted({clause.policy for clause in load_clauses()})


# Title-casing gets "Hdfc Ergo". These are brand names on a dropdown the
# insured will recognise, so the three indexed ones are spelled out.
DISPLAY_NAMES = {
    "star_health": "Star Health",
    "hdfc_ergo": "HDFC ERGO",
    "niva_bupa": "Niva Bupa",
}


def display_name(policy: str) -> str:
    """An uploaded policy falls back to a readable version of its filename."""
    return DISPLAY_NAMES.get(policy, policy.replace("_", " ").title())


def policy_rows() -> list[dict[str, Any]]:
    """The insurer dropdown: id, display name, clause count, sums insured."""
    counts: dict[str, int] = {}
    for clause in load_clauses():
        counts[clause.policy] = counts.get(clause.policy, 0) + 1
    return [
        {
            "id": policy,
            "name": display_name(policy),
            "clauses": counts[policy],
            # star_health prices its room limit by sum insured, so its dropdown
            # is its own table. The other two defer the room limit to the
            # schedule and get the standard set.
            "sum_insured_options": sum_insured_options(policy),
        }
        for policy in sorted(counts)
    ]


def report_payload(report: AuditReport) -> dict[str, Any]:
    """The report as JSON, with the assumptions lifted out of the trace.

    They are in `trace` already, but a UI should not have to filter a trace to
    find out what was taken on trust - so they are also given their own block.
    """
    payload = report.model_dump()
    payload["assumptions"] = [entry for entry in report.trace if entry.get("assumption")]
    return payload


def read_bill(bill_text: str | None, bill_file: UploadFile | None) -> str:
    """The bill as text, from whichever of the two inputs was given."""
    if bill_file is not None and bill_file.filename:
        raw = bill_file.file.read()
        if len(raw) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"the bill is larger than {settings.max_upload_mb} MB")
        if raw.startswith(PDF_MAGIC):
            raise HTTPException(
                400,
                "PDF bills are not supported yet - paste the bill text, or upload a .txt file",
            )
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(400, "the uploaded bill is not readable as text") from exc
    if bill_text and bill_text.strip():
        return bill_text
    raise HTTPException(400, "give a bill: upload a file or paste the text")


def masked_bill(bill_text: str | None, bill_file: UploadFile | None) -> str:
    """The bill with patient identifiers stripped, before anything stores it.

    Masking is done here, at the edge, rather than left to `parse_bill`. A job
    holds its bill text for as long as the process lives, so an unmasked name
    reaching the job store would outlive the request that carried it.
    """
    return mask_pii(read_bill(bill_text, bill_file))


def build_schedule(
    room_limit_per_day: float | None, room_category: str | None
) -> PolicySchedule | None:
    """The optional fourth input. Blank is a valid answer, not a default.

    Two of the three policies state no room rent figure at all - HDFC defers to
    "the Policy Schedule" and Niva Bupa caps by room category. Left blank, the
    audit abstains on room-dependent lines rather than inventing a limit.
    """
    if room_limit_per_day is None and not room_category:
        return None
    return PolicySchedule(room_limit_per_day=room_limit_per_day, room_category=room_category)


def check_policy(policy: str) -> None:
    available = known_policies()
    if policy not in available:
        raise HTTPException(404, f"unknown policy {policy!r}; indexed policies: {available}")
