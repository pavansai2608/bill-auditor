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


class Clause(BaseModel):
    clause_id: str  # "4.2"
    title: str
    text: str
    page: int
    policy: str
    rule_type: RuleType = "other"


class JudgeOutput(BaseModel):
    """What the LLM returns. It NEVER returns a computed amount."""

    clause_id: str | None
    limit_per_day: float | None = None
    limit_absolute: float | None = None
    percentage: float | None = None
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
