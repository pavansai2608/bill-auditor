"""PyUnit tests for the arithmetic. Nothing here touches a model.

Every number the system reports comes through these functions, so they are
tested harder than anything else in the project. A wrong clause citation is
visible to a reader; a wrong multiplication is not.
"""

import unittest

from core.models import BillLine, JudgeOutput
from core.money import (
    allowed_for_line,
    apply_copay,
    cap_to_sum_insured,
    proportionate_ratio,
)


def judge(**kwargs) -> JudgeOutput:
    base = {"clause_id": "4.2", "confident": True, "reasoning": "test"}
    return JudgeOutput(**{**base, **kwargs})


class PerDayLimitTest(unittest.TestCase):
    def test_charge_above_the_cap_is_reduced(self):
        line = BillLine(item="room rent", amount=40000, qty=5)
        allowed, over = allowed_for_line(line, judge(limit_per_day=5000), 500000)
        self.assertEqual(allowed, 25000)
        self.assertTrue(over)

    def test_charge_below_the_cap_is_paid_in_full(self):
        line = BillLine(item="room rent", amount=20000, qty=5)
        allowed, over = allowed_for_line(line, judge(limit_per_day=5000), 500000)
        self.assertEqual(allowed, 20000)
        self.assertFalse(over)

    def test_charge_exactly_at_the_cap_is_not_over_limit(self):
        """The boundary that decides whether the whole bill gets re-scaled."""
        line = BillLine(item="room rent", amount=25000, qty=5)
        allowed, over = allowed_for_line(line, judge(limit_per_day=5000), 500000)
        self.assertEqual(allowed, 25000)
        self.assertFalse(over, "at the limit is within the limit")

    def test_single_day_stay(self):
        line = BillLine(item="room rent", amount=8000, qty=1)
        allowed, over = allowed_for_line(line, judge(limit_per_day=5000), 500000)
        self.assertEqual(allowed, 5000)
        self.assertTrue(over)

    def test_a_zero_limit_excludes_the_item(self):
        line = BillLine(item="gloves", amount=1200, qty=1)
        allowed, over = allowed_for_line(line, judge(limit_per_day=0), 500000)
        self.assertEqual(allowed, 0)
        self.assertTrue(over)


class AbsoluteAndPercentageTest(unittest.TestCase):
    def test_absolute_cap(self):
        line = BillLine(item="ambulance", amount=3000, qty=1)
        allowed, over = allowed_for_line(line, judge(limit_absolute=2000), 500000)
        self.assertEqual(allowed, 2000)
        self.assertFalse(over, "an absolute cap must not trigger proportionate deduction")

    def test_absolute_zero_means_excluded(self):
        line = BillLine(item="baby food", amount=900, qty=1)
        allowed, _ = allowed_for_line(line, judge(limit_absolute=0), 500000)
        self.assertEqual(allowed, 0)

    def test_percentage_is_of_sum_insured_not_of_the_bill(self):
        """1% of 5,00,000 is 5,000 - not 1% off a 40,000 charge."""
        line = BillLine(item="room rent", amount=40000, qty=1)
        allowed, _ = allowed_for_line(line, judge(percentage=1), 500000)
        self.assertEqual(allowed, 5000)

    def test_no_limit_means_paid_in_full(self):
        line = BillLine(item="surgeon fee", amount=80000, qty=1)
        allowed, over = allowed_for_line(line, judge(), 500000)
        self.assertEqual(allowed, 80000)
        self.assertFalse(over)

    def test_per_day_wins_when_several_limits_are_returned(self):
        line = BillLine(item="room rent", amount=40000, qty=5)
        allowed, over = allowed_for_line(
            line, judge(limit_per_day=5000, limit_absolute=90000, percentage=50), 500000
        )
        self.assertEqual(allowed, 25000)
        self.assertTrue(over)


class CopayTest(unittest.TestCase):
    def test_twenty_percent_copay(self):
        self.assertEqual(apply_copay(100000, 20), 80000)

    def test_zero_copay_changes_nothing(self):
        self.assertEqual(apply_copay(100000, 0), 100000)

    def test_full_copay_pays_nothing(self):
        self.assertEqual(apply_copay(100000, 100), 0)


class SumInsuredCapTest(unittest.TestCase):
    def test_total_is_capped(self):
        self.assertEqual(cap_to_sum_insured(620000, 500000), 500000)

    def test_total_below_the_cap_is_untouched(self):
        self.assertEqual(cap_to_sum_insured(136250, 500000), 136250)


class ProportionateRatioTest(unittest.TestCase):
    def test_the_worked_example(self):
        """5,000 eligible against 8,000 charged scales everything to 62.5%."""
        self.assertEqual(proportionate_ratio(5000, 8000), 0.625)
        self.assertEqual(round(80000 * 0.625), 50000)
        self.assertEqual(round(60000 * 0.625), 37500)
        self.assertEqual(round(38000 * 0.625), 23750)

    def test_within_the_limit_gives_no_reduction(self):
        self.assertEqual(proportionate_ratio(5000, 4000), 1.0)

    def test_exactly_at_the_limit_gives_no_reduction(self):
        self.assertEqual(proportionate_ratio(5000, 5000), 1.0)

    def test_zero_rate_is_safe(self):
        """A zero-day stay must not divide by zero."""
        self.assertEqual(proportionate_ratio(5000, 0), 1.0)


if __name__ == "__main__":
    unittest.main()
