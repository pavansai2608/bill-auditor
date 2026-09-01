"""PyUnit tests for the arithmetic. Nothing here touches a model.

Every number the system reports comes through these functions, so they are
tested harder than anything else in the project. A wrong clause citation is
visible to a reader; a wrong multiplication is not.
"""

import unittest

from core.models import BillLine, JudgeOutput, Limit
from core.money import (
    allowed_for_line,
    apply_copay,
    cap_to_sum_insured,
    per_day_limit,
    proportionate_ratio,
    resolve_limit,
)


def judge(*limits: Limit) -> JudgeOutput:
    return JudgeOutput(clause_id="4.2", limits=list(limits), confident=True, reasoning="test")


def per_day(amount):
    return Limit(amount=amount, basis="per_day")


def absolute(amount):
    return Limit(amount=amount, basis="absolute")


def pct_of_si(percentage, basis="absolute"):
    return Limit(percentage=percentage, of="sum_insured", basis=basis)


class PerDayLimitTest(unittest.TestCase):
    def test_charge_above_the_cap_is_reduced(self):
        line = BillLine(item="room rent", amount=40000, qty=5)
        allowed, over = allowed_for_line(line, judge(per_day(5000)), 500000)
        self.assertEqual(allowed, 25000)
        self.assertTrue(over)

    def test_charge_below_the_cap_is_paid_in_full(self):
        line = BillLine(item="room rent", amount=20000, qty=5)
        allowed, over = allowed_for_line(line, judge(per_day(5000)), 500000)
        self.assertEqual(allowed, 20000)
        self.assertFalse(over)

    def test_charge_exactly_at_the_cap_is_not_over_limit(self):
        """The boundary that decides whether the whole bill gets re-scaled."""
        line = BillLine(item="room rent", amount=25000, qty=5)
        allowed, over = allowed_for_line(line, judge(per_day(5000)), 500000)
        self.assertEqual(allowed, 25000)
        self.assertFalse(over, "at the limit is within the limit")

    def test_single_day_stay(self):
        line = BillLine(item="room rent", amount=8000, qty=1)
        allowed, over = allowed_for_line(line, judge(per_day(5000)), 500000)
        self.assertEqual(allowed, 5000)
        self.assertTrue(over)

    def test_a_zero_limit_excludes_the_item(self):
        line = BillLine(item="gloves", amount=1200, qty=1)
        allowed, over = allowed_for_line(line, judge(per_day(0)), 500000)
        self.assertEqual(allowed, 0)
        self.assertTrue(over)


class AbsoluteAndPercentageTest(unittest.TestCase):
    def test_absolute_cap(self):
        line = BillLine(item="ambulance", amount=3000, qty=1)
        allowed, over = allowed_for_line(line, judge(absolute(2000)), 500000)
        self.assertEqual(allowed, 2000)
        self.assertFalse(over, "an absolute cap must not trigger proportionate deduction")

    def test_absolute_zero_means_excluded(self):
        line = BillLine(item="baby food", amount=900, qty=1)
        allowed, _ = allowed_for_line(line, judge(absolute(0)), 500000)
        self.assertEqual(allowed, 0)

    def test_percentage_is_of_sum_insured_not_of_the_bill(self):
        """1% of 5,00,000 is 5,000 - not 1% off a 40,000 charge."""
        line = BillLine(item="room rent", amount=40000, qty=1)
        allowed, _ = allowed_for_line(line, judge(pct_of_si(1)), 500000)
        self.assertEqual(allowed, 5000)

    def test_no_limit_means_paid_in_full(self):
        line = BillLine(item="surgeon fee", amount=80000, qty=1)
        allowed, over = allowed_for_line(line, judge(), 500000)
        self.assertEqual(allowed, 80000)
        self.assertFalse(over)

    def test_lowest_limit_wins_when_several_are_stated(self):
        line = BillLine(item="room rent", amount=40000, qty=5)
        allowed, over = allowed_for_line(
            line, judge(per_day(5000), absolute(90000), pct_of_si(50)), 500000
        )
        self.assertEqual(allowed, 25000, "5,000 x 5 days is the lowest of the three")
        self.assertTrue(over)


class MultipleLimitsTest(unittest.TestCase):
    """The two shapes that a single limit field could not express."""

    def test_two_units_in_one_sentence(self):
        """star_health II.8: Rs 750 per hospitalisation AND Rs 1,500 per policy period."""
        line = BillLine(item="ambulance charges", amount=3000, qty=1)
        allowed, over = allowed_for_line(
            line,
            judge(
                Limit(amount=750, basis="per_hospitalization"),
                Limit(amount=1500, basis="per_policy_period"),
            ),
            500000,
        )
        self.assertEqual(allowed, 750, "the per-hospitalisation cap is the lower one")
        self.assertFalse(over)

    def test_percentage_or_rupee_cap_whichever_is_less(self):
        """star_health II.11: 10% of Sum Insured or Rs 1,00,000, whichever is less."""
        line = BillLine(item="organ donor expenses", amount=250000, qty=1)
        limits = (pct_of_si(10), absolute(100000))

        # At 5,00,000 the percentage binds: 10% is 50,000.
        allowed, _ = allowed_for_line(line, judge(*limits), 500000)
        self.assertEqual(allowed, 50000)

        # At 25,00,000 the rupee cap binds: 10% would be 2,50,000.
        allowed, _ = allowed_for_line(line, judge(*limits), 2500000)
        self.assertEqual(allowed, 100000)

    def test_neither_limit_is_silently_discarded(self):
        """The bug this replaced: one field meant one limit survived."""
        line = BillLine(item="ambulance", amount=900, qty=1)
        output = judge(
            Limit(amount=750, basis="per_hospitalization"),
            Limit(amount=1500, basis="per_policy_period"),
        )
        self.assertEqual(len(output.limits), 2)
        self.assertEqual(allowed_for_line(line, output, 500000)[0], 750)

    def test_per_day_breach_still_flags_for_the_second_pass(self):
        line = BillLine(item="room rent", amount=40000, qty=5)
        _, over = allowed_for_line(line, judge(per_day(5000), absolute(90000)), 500000)
        self.assertTrue(over, "a breached per-day cap must trigger proportionate deduction")

    def test_absolute_breach_does_not_flag(self):
        line = BillLine(item="ambulance", amount=3000, qty=1)
        _, over = allowed_for_line(line, judge(absolute(750)), 500000)
        self.assertFalse(over)


class ResolveLimitTest(unittest.TestCase):
    def test_per_day_multiplies_by_days(self):
        line = BillLine(item="room rent", amount=40000, qty=5)
        self.assertEqual(resolve_limit(per_day(5000), line, 500000), 25000)

    def test_other_bases_cap_the_line_as_a_whole(self):
        line = BillLine(item="ambulance", amount=3000, qty=4)
        for basis in ("absolute", "per_hospitalization", "per_policy_period"):
            with self.subTest(basis=basis):
                limit = Limit(amount=750, basis=basis)
                self.assertEqual(resolve_limit(limit, line, 500000), 750)

    def test_percentage_resolves_against_sum_insured(self):
        line = BillLine(item="organ donor", amount=99999, qty=1)
        self.assertEqual(resolve_limit(pct_of_si(10), line, 500000), 50000)

    def test_an_empty_limit_resolves_to_nothing(self):
        line = BillLine(item="x", amount=100, qty=1)
        self.assertIsNone(resolve_limit(Limit(basis="absolute"), line, 500000))

    def test_per_day_limit_reports_the_rate_not_the_total(self):
        """The second pass needs the rate to build its ratio."""
        self.assertEqual(per_day_limit(judge(per_day(5000), absolute(90000))), 5000)
        self.assertIsNone(per_day_limit(judge(absolute(90000))))


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
