"""Assumptions the audit has to make, recorded rather than hidden.

Some rules depend on facts the inputs cannot carry. The clearest is
proportionate deduction: both Star Health and HDFC disapply it "in respect of
the hospitals which do not follow differential billing", and nothing on a bill
says whether the hospital does. Refusing to audit any bill because that cannot
be verified would make the system useless; assuming it silently would make the
system dishonest. So the assumption is made, and stated - in the trace, in the
report, and in the README - with the clause text that carries the carve-out.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Assumption:
    name: str
    holds: bool
    statement: str
    because: str
    clause_id: str | None = None
    clause_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption": self.name,
            "assumed": self.holds,
            "statement": self.statement,
            "because": self.because,
            "clause_id": self.clause_id,
            "clause_text": self.clause_text,
        }


DIFFERENTIAL_BILLING = "differential_billing"
LLM_FALLBACK = "llm_backend_fallback"

LLM_FALLBACK_STATEMENT = (
    "the hosted model became unavailable part way through, so the rest of this "
    "audit was decided by the local model"
)
LLM_FALLBACK_WHY = (
    "Two things end a hosted run: the free tier's daily request limit, and the "
    "network. Either way, finishing on the local model is slower but complete; "
    "stopping half way would leave a report that looks finished and is not. The "
    "two models do not always agree, so the lines after the switch were judged "
    "by a different model from the lines before it."
)

DIFFERENTIAL_BILLING_STATEMENT = (
    "assumed the hospital follows differential billing, so proportionate deduction applies"
)
DIFFERENTIAL_BILLING_WHY = (
    "the policy disapplies proportionate deduction at hospitals that do not "
    "bill differentially, and nothing on a bill states whether this one does. "
    "This was assumed, not verified - pass --no-differential-billing to turn "
    "it off."
)


@dataclass
class Assumptions:
    """The set in force for one audit."""

    differential_billing: bool = True
    recorded: list[Assumption] = field(default_factory=list)

    def note_differential_billing(
        self, clause_id: str | None = None, clause_text: str | None = None
    ) -> Assumption:
        statement = (
            DIFFERENTIAL_BILLING_STATEMENT
            if self.differential_billing
            else "differential billing was ruled out, so proportionate deduction does not apply"
        )
        entry = Assumption(
            name=DIFFERENTIAL_BILLING,
            holds=self.differential_billing,
            statement=statement,
            because=DIFFERENTIAL_BILLING_WHY,
            clause_id=clause_id,
            clause_text=(clause_text or "")[:400] or None,
        )
        self.recorded.append(entry)
        return entry

    def note_llm_fallback(self, reason: str) -> Assumption:
        """Record that the backend changed mid-audit. Never silent."""
        entry = Assumption(
            name=LLM_FALLBACK,
            holds=True,
            statement=LLM_FALLBACK_STATEMENT,
            because=f"{LLM_FALLBACK_WHY} The backend reported: {reason}",
        )
        self.recorded.append(entry)
        return entry

    def as_trace(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self.recorded]
