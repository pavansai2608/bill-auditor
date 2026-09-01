"""All arithmetic. No LLM ever computes a number.

Every function is pure and takes the limits the model *read from the clause*,
never a figure it worked out. An 8B model asked to multiply 5,000 by 5 will
sometimes answer 20,000 and sound certain, and a wrong total is invisible in a
way a wrong citation is not.
"""

from core.models import BillLine, JudgeOutput, Limit


def resolve_limit(limit: Limit, line: BillLine, sum_insured: float) -> float | None:
    """Turn one stated limit into the rupee ceiling it puts on this line.

    A percentage is always of the sum insured, because that is the only base
    these policies use. A per-day figure is multiplied by the days billed;
    every other basis caps the line as a whole.
    """
    if limit.percentage is not None and limit.of == "sum_insured":
        base = sum_insured * limit.percentage / 100
    elif limit.amount is not None:
        base = float(limit.amount)
    else:
        return None

    if limit.basis == "per_day":
        return base * line.qty
    return base


def allowed_for_line(line: BillLine, judge: JudgeOutput, sum_insured: float) -> tuple[float, bool]:
    """What is payable for one line, and whether a per-day cap was breached.

    Where a clause states several limits they all apply, so the lowest wins.
    That single rule covers both awkward shapes: "Rs 750 per hospitalisation
    and Rs 1,500 per policy period", and "10% of Sum Insured or Rs 1,00,000,
    whichever is less".

    `over_limit` marks a breached *per-day* cap specifically, because that is
    what triggers the proportionate-deduction second pass. An absolute cap
    reduces one line and nothing else.
    """
    charged = line.amount

    resolved = [
        (limit, value)
        for limit in judge.limits
        if (value := resolve_limit(limit, line, sum_insured)) is not None
    ]
    if not resolved:
        # No limit stated means the clause allows the charge in full.
        return round(charged, 2), False

    ceiling = min(value for _, value in resolved)
    over_limit = any(limit.basis == "per_day" and charged > value for limit, value in resolved)
    return round(min(charged, ceiling), 2), over_limit


def per_day_limit(judge: JudgeOutput) -> float | None:
    """The per-day rate itself, which the second pass needs for its ratio."""
    rates = [
        limit.amount
        for limit in judge.limits
        if limit.basis == "per_day" and limit.amount is not None
    ]
    return min(rates) if rates else None


def apply_copay(allowed: float, percentage: float) -> float:
    """Co-payment is the share the insured bears, taken off what is allowed."""
    return round(allowed * (1 - percentage / 100), 2)


def cap_to_sum_insured(allowed_total: float, sum_insured: float) -> float:
    """No policy pays more than the sum insured, whatever the lines add up to."""
    return round(min(allowed_total, sum_insured), 2)


def proportionate_ratio(eligible_limit: float, charged_rate: float) -> float:
    """The ratio every other line is scaled by when room rent is breached.

    5,000 eligible against 8,000 charged gives 0.625, and the surgeon's fee,
    ICU and medicines are all reduced to 62.5%.
    """
    if charged_rate <= 0:
        return 1.0
    return min(1.0, eligible_limit / charged_rate)
