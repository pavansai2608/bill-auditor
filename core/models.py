"""Data models shared by every layer.

These are the contract between the retriever, the agent and the API. The one
rule that shapes them: `JudgeOutput` carries no computed amount. The model
reports the *limit* it found and the clause it came from; Python does the
arithmetic and fills in `LineVerdict.allowed`.
"""

from typing import Literal

from pydantic import BaseModel, Field

RuleType = Literal[
    "room_rent",
    "non_payable",
    "sub_limit",
    "copay",
    "waiting_period",
    "other",
]


class BillLine(BaseModel):
    item: str
    amount: float = Field(gt=0)
    qty: int = Field(default=1, ge=1)


class PolicySchedule(BaseModel):
    """The room entitlement printed on the insured's own policy schedule.

    Two of the three policies state no room rent figure in the wording at all:
    HDFC's is "At Actuals unless otherwise specified in the Policy Schedule",
    and Niva Bupa caps by room category "as specified in your Policy Schedule".
    Without this the proportionate deduction is not computable for them, and
    the honest answer is to say so rather than assume a limit.

    Optional by design. Blank is a valid answer that produces an abstention.
    """

    room_limit_per_day: float | None = None
    room_category: str | None = None

    def is_empty(self) -> bool:
        return self.room_limit_per_day is None and not self.room_category


class Clause(BaseModel):
    clause_id: str  # "4.2"
    title: str
    text: str
    page: int
    policy: str
    rule_type: RuleType = "other"
    # Clause ids this clause names. Star Health's co-payment applies only to
    # "Coverages II.1, II.2, ... II.13", and its specified-disease waiting
    # period says the longer of two periods applies - neither is decidable
    # from the clause alone. Referenced clauses are retrieved alongside it.
    refs: list[str] = []


class Limit(BaseModel):
    """One limit as the clause states it, with its unit kept intact.

    Three separate fields could not hold what the wording actually says. Star
    Health's road ambulance clause carries two limits in one sentence - "up to
    Rs.750/- per hospitalization and up to Rs.1,500/- per Policy Period" - and
    several benefits are capped at "10% of Sum Insured or Rs 1,00,000,
    whichever is less". A single field forced the model to discard one of them
    silently. A list keeps every limit the clause states; Python resolves each
    to rupees for this bill and takes the lowest.
    """

    amount: float | None = None  # a rupee figure
    percentage: float | None = None  # e.g. 10.0
    of: Literal["sum_insured"] | None = None
    basis: Literal["per_day", "per_hospitalization", "per_policy_period", "absolute"]


class JudgeOutput(BaseModel):
    """What the LLM returns. It NEVER returns a computed amount."""

    clause_id: str | None
    limits: list[Limit] = []
    confident: bool
    reasoning: str


class LineVerdict(BaseModel):
    item: str
    charged: float
    allowed: float | None
    clause_id: str | None
    reason: str
    needs_human: bool = False
    over_limit: bool = False
    limit_per_day: float | None = None


class AuditReport(BaseModel):
    lines: list[LineVerdict]
    total_charged: float
    total_allowed: float
    flagged_count: int
    policy: str
    trace: list[dict] = []


class ComparisonReport(BaseModel):
    reports: list[AuditReport]
    best_policy: str
    difference: float
