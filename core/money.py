"""All arithmetic. No LLM ever computes a number.

Every function here is pure and takes a `JudgeOutput` - the limit the model
found - plus the billed amount. An 8B model asked to multiply 5,000 by 5 will
sometimes answer 20,000 and sound completely certain, and a wrong total is
invisible in a way a wrong clause citation is not.
"""

from core.models import BillLine, JudgeOutput


def allowed_for_line(line: BillLine, judge: JudgeOutput, sum_insured: float) -> tuple[float, bool]:
    """Work out what is payable for one line.

    Returns (allowed, over_limit). `over_limit` marks a per-day cap that was
    breached, which is what triggers the proportionate-deduction second pass
    later - so it is set only for per-day limits, not for every reduction.
    """
    charged = line.amount

    if judge.limit_per_day is not None:
        cap = judge.limit_per_day * line.qty
        allowed = min(charged, cap)
        return round(allowed, 2), charged > cap

    if judge.limit_absolute is not None:
        return round(min(charged, judge.limit_absolute), 2), False

    if judge.percentage is not None:
        # A percentage in a policy clause is a cap expressed against the sum
        # insured ("1% of Sum Insured per day"), not a discount on the bill.
        cap = sum_insured * judge.percentage / 100
        return round(min(charged, cap), 2), False

    # No limit found means the clause allows the charge in full.
    return round(charged, 2), False


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
