"""The agent loop: one bill line in, one cited verdict or an honest abstention out.

A LangGraph state machine rather than a straight line, because the naive audit
(v0) failed in a specific way: it searched once, and when that one query missed,
it gave up. Measured on the first ten bills it flagged 42 lines the answer key
can answer - it was not confidently wrong so much as unwilling.

    check_non_payable -> classify -> build_query -> retrieve -> judge -> grade
                                          ^                                |
                                          +---------- rewrite -------------+

Three things bound the loop, so it cannot spin:

* three attempts, then abstain
* eight tool calls per line, hard
* if two consecutive rounds retrieve the same clauses, stop early - a third
  identical round will not tell us anything the first two did not

The fast path matters for cost as much as accuracy. An item on the IRDAI
non-payable list is settled without a search or a model call, and roughly a
third of real bill lines are consumables.
"""

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.config import settings
from core.ingest import load_non_payable
from core.llm import LLMError, complete_structured
from core.logging_conf import TraceWriter, get_logger
from core.models import (
    BillLine,
    JudgeOutput,
    Limit,
    LineVerdict,
    PolicySchedule,
    RuleType,
)
from core.money import allowed_for_line, per_day_limit
from core.retrieve import RetrievedClause, search
from core.room_limit import lookup as room_lookup
from core.room_limit import room_rank

log = get_logger(__name__)

IRDAI_CITATION = "IRDAI-List-I"

# "Ambulance" is IRDAI List I #67, but every policy also carries a named
# ambulance benefit with its own limit. The benefit clause decides it, so the
# fast path must not claim it - the list entry covers ambulance equipment
# billed as an item, not the journey.
BENEFIT_OVERRIDES_LIST_RE = re.compile(r"ambulance", re.I)

# Deterministic rule-type routing. A model call per line to classify would add
# seven seconds a line to answer something a dozen keywords settle.
RULE_PATTERNS: list[tuple[RuleType, re.Pattern]] = [
    ("room_rent", re.compile(r"room rent|room charges|bed charges|accommodation", re.I)),
    ("copay", re.compile(r"co-?pay", re.I)),
    (
        "waiting_period",
        re.compile(
            r"cataract|hernia|knee replacement|joint replacement|hysterectomy|piles|fistula", re.I
        ),
    ),
    (
        "sub_limit",
        re.compile(
            r"ambulance|ayush|robotic|stem cell|maternity|dental|physiotherap|cataract", re.I
        ),
    ),
]

# Each attempt asks from a different angle. Repeating a query that already
# missed is the one thing a retry must never do.
QUERY_ANGLES: dict[RuleType, list[str]] = {
    "room_rent": [
        "room rent limit per day eligible room category",
        "proportionate deduction associated medical expenses room category exceeded",
        "boarding nursing expenses hospital accommodation entitlement",
    ],
    "sub_limit": [
        "{item} sub-limit maximum payable",
        "{item} limit per policy period per treatment",
        "benefit limit expenses payable for {item}",
    ],
    "waiting_period": [
        "{item} waiting period specified disease exclusion",
        "months of continuous coverage before this treatment is covered",
        "listed conditions excluded until expiry of waiting period",
    ],
    "copay": [
        "co-payment percentage of claim amount",
        "share of claim borne by the insured person",
        "deductible co-pay applicable to this policy",
    ],
    "non_payable": [
        "{item} excluded expense not payable",
        "non-medical items excluded from the claim",
        "items for which coverage is not available",
    ],
    "other": [
        "{item} limit coverage",
        "expenses payable for {item} during hospitalization",
        "{item} exclusion or cap under this policy",
    ],
}


class AgentState(TypedDict, total=False):
    line: BillLine
    sum_insured: float
    policy: str
    schedule: PolicySchedule | None
    valid_ids: set[str]
    rule_type: RuleType
    query: str
    candidates: list[RetrievedClause]
    attempts: int
    tool_calls: int
    seen: list[frozenset]
    verdict: LineVerdict | None
    reason: str
    fabricated: bool
    resolved_on: int
    judge_calls: int
    trace: list[dict[str, Any]]
    # LangGraph passes on only the keys declared here. Anything a node writes
    # under another name is silently dropped between nodes - which cost a
    # correct verdict on the first attempt until it was found.
    judge_output: JudgeOutput | None
    writer: Any


# --------------------------------------------------------------------------
# nodes
# --------------------------------------------------------------------------


def _note(state: AgentState, node: str, **fields: Any) -> None:
    record = {"node": node, "attempt": state.get("attempts", 0), **fields}
    state.setdefault("trace", []).append(record)
    writer = state.get("writer")
    if writer is not None:
        writer.step(node, item=state["line"].item, **fields)


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z ]", " ", text.lower())


def check_non_payable(state: AgentState) -> AgentState:
    """Path A - settle excluded consumables with no search and no model call."""
    if BENEFIT_OVERRIDES_LIST_RE.search(state["line"].item):
        _note(state, "check_non_payable", hit=None, skipped="named benefit takes precedence")
        return state

    item = _normalise(state["line"].item)
    for entry in load_non_payable():
        name = _normalise(re.split(r"[(/-]", entry["item"])[0])
        if len(name.strip()) > 3 and name.strip() in item:
            line = state["line"]
            state["verdict"] = LineVerdict(
                item=line.item,
                charged=line.amount,
                allowed=0.0,
                clause_id=IRDAI_CITATION,
                reason=f"{entry['item']} is item #{entry['no']} on the IRDAI "
                f"non-payable list, so nothing is payable",
            )
            _note(state, "check_non_payable", hit=entry["item"], irdai_no=entry["no"])
            return state
    _note(state, "check_non_payable", hit=None)
    return state


def classify(state: AgentState) -> AgentState:
    item = state["line"].item
    rule_type: RuleType = "other"
    for candidate, pattern in RULE_PATTERNS:
        if pattern.search(item):
            rule_type = candidate
            break
    state["rule_type"] = rule_type
    _note(state, "classify", rule_type=rule_type)
    return state


def room_limit(state: AgentState) -> AgentState:
    """Path B - settle the room line from the table, with no model call.

    Room rent is a lookup: policy plus sum insured names the row. Asking the
    model to read that table cost a wrong figure on B05 - 800/day against a
    table granting a room category - and because room rent gates the second
    pass, that one figure rescaled three further lines. The model cannot
    misread a number it is never shown.

    Only a row that does not exist falls through to the judge, and the trace
    says so, because a silent fallback would look exactly like a lookup.
    """
    from core.audit import SCHEDULE_MISSING_REASON

    if state["rule_type"] != "room_rent":
        return state

    line = state["line"]
    entitlement = room_lookup(state["policy"], state["sum_insured"], state.get("schedule"))

    if entitlement is None:
        _note(
            state,
            "room_limit",
            resolved=False,
            fallback="judge",
            why=f"no room rent table row for sum insured {int(state['sum_insured']):,}",
        )
        return state

    if entitlement.per_day is not None:
        output = JudgeOutput(
            clause_id=entitlement.clause_id,
            limits=[Limit(amount=entitlement.per_day, basis="per_day")],
            confident=True,
            reasoning=entitlement.source,
        )
        allowed, over_limit = allowed_for_line(line, output, state["sum_insured"])
        state["verdict"] = LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=allowed,
            clause_id=entitlement.clause_id,
            reason=(
                f"{entitlement.source}; {entitlement.per_day:,.0f} x {line.qty} = "
                f"{entitlement.per_day * line.qty:,.0f}, "
                f"min({line.amount:,.0f}, {entitlement.per_day * line.qty:,.0f}) = {allowed:,.0f}"
            ),
            over_limit=over_limit,
            limit_per_day=entitlement.per_day,
        )
    elif entitlement.at_actuals:
        state["verdict"] = LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=round(line.amount, 2),
            clause_id=entitlement.clause_id,
            reason=f"{entitlement.source}, so the room charge is payable in full",
        )
    elif entitlement.category:
        occupied = room_rank(line.item)
        entitled = room_rank(entitlement.category)
        if occupied is not None and entitled is not None and occupied <= entitled:
            state["verdict"] = LineVerdict(
                item=line.item,
                charged=line.amount,
                allowed=round(line.amount, 2),
                clause_id=entitlement.clause_id,
                reason=(
                    f"{entitlement.source}; the room occupied is at or below that "
                    "category, so nothing is deducted"
                ),
            )
        else:
            # A room above the entitlement does breach it, but the policy
            # states no rupee figure to build a ratio from. Guessing one would
            # produce a confident deduction with nothing behind it.
            state["verdict"] = LineVerdict(
                item=line.item,
                charged=line.amount,
                allowed=None,
                clause_id=entitlement.clause_id,
                reason=(
                    f"{entitlement.source}, and the room billed is not clearly within "
                    "it - no rupee limit exists to compute a deduction from"
                ),
                needs_human=True,
            )
    else:  # defers to the schedule, and none was given
        state["verdict"] = LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=entitlement.clause_id,
            reason=SCHEDULE_MISSING_REASON,
            needs_human=True,
        )

    verdict = state["verdict"]
    _note(
        state,
        "room_limit",
        resolved=True,
        clause_id=entitlement.clause_id,
        per_day=entitlement.per_day,
        category=entitlement.category,
        source=entitlement.source,
        allowed=verdict.allowed,
        needs_human=verdict.needs_human,
    )
    return state


def build_query(state: AgentState) -> AgentState:
    """Pick the angle for this attempt. Never the same query twice."""
    angles = QUERY_ANGLES.get(state["rule_type"], QUERY_ANGLES["other"])
    attempt = min(state.get("attempts", 0), len(angles) - 1)
    item = re.sub(r"[\d,]+\s*x\s*\d+\s*days?|\(.*?\)|[\d,]{4,}", "", state["line"].item).strip()
    state["query"] = angles[attempt].format(item=item or state["line"].item)
    _note(state, "build_query", query=state["query"])
    return state


def retrieve(state: AgentState) -> AgentState:
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    state["candidates"] = search(state["query"], state["policy"])
    ids = frozenset(c.clause.clause_id for c in state["candidates"])
    state.setdefault("seen", []).append(ids)
    _note(
        state,
        "retrieve",
        clauses=sorted(ids),
        top_score=round(state["candidates"][0].score, 3) if state["candidates"] else None,
    )
    return state


def judge(state: AgentState) -> AgentState:
    """Ask what limits the retrieved clauses state. Never what the amount is."""
    from core.audit import JUDGE_SYSTEM, _judge_prompt

    candidates = state["candidates"]
    if not candidates:
        state["reason"] = "nothing was retrieved for this query"
        _note(state, "judge", skipped="no candidates")
        return state

    # Guardrail 5: if nothing scored well, the model would be reasoning over
    # clauses that do not apply. Cheaper and safer to rewrite the query.
    best = max(c.score for c in candidates)
    if best < settings.rerank_score_threshold:
        state["reason"] = f"best clause scored {best:.2f}, below the relevance threshold"
        _note(state, "judge", skipped="below threshold", top_score=round(best, 3))
        return state

    state["tool_calls"] = state.get("tool_calls", 0) + 1
    state["judge_calls"] = state.get("judge_calls", 0) + 1
    try:
        output = complete_structured(
            _judge_prompt(state["line"], candidates, state["sum_insured"], state.get("schedule")),
            JudgeOutput,
            system=JUDGE_SYSTEM,
        )
    except LLMError as exc:
        state["reason"] = "the model could not produce a usable verdict"
        _note(state, "judge", error=str(exc)[:120])
        return state

    state["judge_output"] = output
    _note(
        state,
        "judge",
        clause_id=output.clause_id,
        confident=output.confident,
        limits=[limit.model_dump() for limit in output.limits],
    )
    return state


def grade(state: AgentState) -> AgentState:
    """Accept, retry from a different angle, or abstain. Nothing else."""
    output = state.pop("judge_output", None)
    line = state["line"]

    if output is None:
        state["attempts"] = state.get("attempts", 0) + 1
        _note(state, "grade", decision="rewrite", why=state.get("reason", "no output"))
        return state

    if not output.confident:
        state["attempts"] = state.get("attempts", 0) + 1
        state["reason"] = output.reasoning or "the model was not confident"
        _note(state, "grade", decision="rewrite", why="not confident")
        return state

    # Guardrail 2: a citation that is not in this policy is rejected outright.
    # The model was confident, so re-asking would only put the same question to
    # it again - and re-asking a confident answer is exactly where latency goes
    # for no accuracy gain. Abstain instead.
    if output.clause_id not in state["valid_ids"]:
        state["fabricated"] = True
        state["reason"] = f"cited clause {output.clause_id!r} does not exist in this policy"
        _note(
            state,
            "grade",
            decision="abstain",
            why="fabricated citation",
            clause_id=output.clause_id,
        )
        return state

    from core.audit import SCHEDULE_MISSING_REASON, _defers_to_schedule

    schedule = state.get("schedule")
    given = schedule is not None and not schedule.is_empty()
    if not output.limits and not given and _defers_to_schedule(state["candidates"]):
        state["verdict"] = LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=output.clause_id,
            reason=SCHEDULE_MISSING_REASON,
            needs_human=True,
        )
        _note(state, "grade", decision="abstain", why="schedule not provided")
        return state

    if not output.limits and given and schedule.room_limit_per_day is not None:
        output = output.model_copy(
            update={"limits": [Limit(amount=schedule.room_limit_per_day, basis="per_day")]}
        )

    state["resolved_on"] = state.get("attempts", 0) + 1
    allowed, over_limit = allowed_for_line(line, output, state["sum_insured"])
    state["verdict"] = LineVerdict(
        item=line.item,
        charged=line.amount,
        allowed=allowed,
        clause_id=output.clause_id,
        reason=output.reasoning,
        over_limit=over_limit,
        limit_per_day=per_day_limit(output),
    )
    _note(state, "grade", decision="save", clause_id=output.clause_id, allowed=allowed)
    return state


def _why_stopped(state: AgentState) -> str:
    """Explain the stop from the state itself.

    The decision is made in a conditional edge, and LangGraph does not merge
    anything an edge function writes - so the reason has to be re-derived here
    or it is silently lost.
    """
    detail = state.get("reason") or "the query kept missing"
    seen = state.get("seen", [])
    if state.get("fabricated"):
        return detail
    if len(seen) >= 2 and seen[-1] == seen[-2] and seen[-1]:
        return f"two consecutive searches returned the same clauses; {detail}"
    if state.get("tool_calls", 0) >= settings.max_tool_calls:
        return f"reached the cap of {settings.max_tool_calls} tool calls; {detail}"
    if state.get("attempts", 0) >= settings.max_attempts:
        return f"no clause found after {settings.max_attempts} attempts: {detail}"
    return detail


def abstain(state: AgentState) -> AgentState:
    line = state["line"]
    state["verdict"] = LineVerdict(
        item=line.item,
        charged=line.amount,
        allowed=None,
        clause_id=None,
        reason=_why_stopped(state),
        needs_human=True,
    )
    _note(
        state, "abstain", attempts=state.get("attempts", 0), tool_calls=state.get("tool_calls", 0)
    )
    return state


# --------------------------------------------------------------------------
# edges
# --------------------------------------------------------------------------


def after_non_payable(state: AgentState) -> str:
    return "done" if state.get("verdict") else "continue"


def after_room_limit(state: AgentState) -> str:
    """A resolved room line is finished. Everything else goes to retrieval."""
    return "done" if state.get("verdict") else "continue"


def after_grade(state: AgentState) -> str:
    """The stopping rules, in the order they may fire. Pure - decides only."""
    if state.get("verdict"):
        return "done"

    # A confident answer is never re-asked. Only an unconfident one, an empty
    # retrieval, or a below-threshold score earns another angle.
    if state.get("fabricated"):
        return "abstain"

    if state.get("attempts", 0) >= settings.max_attempts:
        return "abstain"

    if state.get("tool_calls", 0) >= settings.max_tool_calls:
        return "abstain"

    # Two rounds returning the same clauses means rewriting is not moving the
    # retriever. A third identical round costs a judge call and tells us nothing.
    seen = state.get("seen", [])
    if len(seen) >= 2 and seen[-1] == seen[-2] and seen[-1]:
        return "abstain"

    return "retry"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("check_non_payable", check_non_payable)
    graph.add_node("classify", classify)
    graph.add_node("room_limit", room_limit)
    graph.add_node("build_query", build_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("judge", judge)
    graph.add_node("grade", grade)
    graph.add_node("abstain", abstain)

    graph.add_edge(START, "check_non_payable")
    graph.add_conditional_edges(
        "check_non_payable", after_non_payable, {"done": END, "continue": "classify"}
    )
    graph.add_edge("classify", "room_limit")
    graph.add_conditional_edges(
        "room_limit", after_room_limit, {"done": END, "continue": "build_query"}
    )
    graph.add_edge("build_query", "retrieve")
    graph.add_edge("retrieve", "judge")
    graph.add_edge("judge", "grade")
    graph.add_conditional_edges(
        "grade", after_grade, {"done": END, "retry": "build_query", "abstain": "abstain"}
    )
    graph.add_edge("abstain", END)
    return graph.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def audit_line(
    line: BillLine,
    policy: str,
    sum_insured: float,
    valid_ids: set[str],
    schedule: PolicySchedule | None = None,
    writer: TraceWriter | None = None,
) -> tuple[LineVerdict, list[dict[str, Any]]]:
    """Run one bill line through the loop. Returns the verdict and its trace."""
    state: AgentState = {
        "line": line,
        "policy": policy,
        "sum_insured": sum_insured,
        "valid_ids": valid_ids,
        "schedule": schedule,
        "attempts": 0,
        "tool_calls": 0,
        "seen": [],
        "trace": [],
    }
    if writer is not None:
        state["writer"] = writer

    # recursion_limit guards against a graph bug; the loop's own caps should
    # always fire first.
    final = get_graph().invoke(state, {"recursion_limit": 40})
    trace = final.get("trace", [])

    # Per-line accounting, so the value of the retry loop is a number rather
    # than an assumption. `retry_changed_answer` is the one that matters: if
    # attempts 2 and 3 rarely turn a non-answer into an answer, the loop is
    # costing latency and buying nothing.
    # Model calls actually made, not judge-node visits: the node logs a step
    # even when it skips the model on a below-threshold retrieval.
    judge_calls = final.get("judge_calls", 0)
    resolved_on = final.get("resolved_on")
    summary = {
        "node": "summary",
        "item": line.item,
        "attempts": max(1, len([r for r in trace if r["node"] == "build_query"])),
        "judge_calls": judge_calls,
        "tool_calls": final.get("tool_calls", 0),
        "resolved_on_attempt": resolved_on,
        "retry_changed_answer": bool(resolved_on and resolved_on > 1),
        "fast_path": judge_calls == 0 and final.get("verdict") is not None,
        "abstained": bool(final.get("verdict") and final["verdict"].needs_human),
    }
    trace.append(summary)
    if writer is not None:
        writer.step("summary", **{k: v for k, v in summary.items() if k != "node"})

    verdict = final.get("verdict")
    if verdict is None:  # pragma: no cover - the graph always ends at a verdict
        verdict = LineVerdict(
            item=line.item,
            charged=line.amount,
            allowed=None,
            clause_id=None,
            reason="the agent finished without reaching a verdict",
            needs_human=True,
        )
    return verdict, trace
