"""Strip patient identifiers before any text reaches the model.

Ordering matters more than cleverness here: masking happens on the raw bill
text, before parsing, so no identifier ever appears in a prompt, a cached
response on disk, or a trace file. A cache entry is the awkward one - it
persists, so a leak there outlives the request that caused it.

This is deliberately conservative. Over-masking costs nothing (a masked phone
number was never going to affect a verdict); under-masking is a privacy breach.
"""

import re

PHONE_RE = re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b")
AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
# "Patient Name: Ramesh Kumar", "Insured: R Kumar", "UHID: SH123456"
LABELLED_RE = re.compile(
    r"(?im)^([ \t]*(?:patient(?:'s)?\s*name|patient|insured(?:\s*name)?|name|"
    r"uhid|mrn|ip\s*no\.?|policy\s*no\.?|member\s*id|claim\s*no\.?)"
    r"[ \t]*[:\-][ \t]*)(.+)$"
)

MASK = "[REDACTED]"


def mask_pii(text: str) -> str:
    """Replace patient identifiers with a placeholder.

    Labelled fields are masked by their label rather than by trying to
    recognise Indian names, which no regex does reliably and a wrong guess on
    would either leak a name or redact a drug.
    """
    masked = LABELLED_RE.sub(lambda m: f"{m.group(1)}{MASK}", text)
    masked = AADHAAR_RE.sub(MASK, masked)
    masked = PHONE_RE.sub(MASK, masked)
    return EMAIL_RE.sub(MASK, masked)


def contains_pii(text: str) -> bool:
    """Used by guardrail 7 to assert nothing slipped through."""
    return bool(PHONE_RE.search(text) or AADHAAR_RE.search(text) or EMAIL_RE.search(text))
