"""PyUnit tests for masking, bill intake and the naive audit.

The model is stubbed throughout. These assert the control flow around it -
particularly that a fabricated citation is rejected - which is what has to hold
regardless of what the model says on any given run.
"""

import unittest
from unittest import mock

from core.audit import audit_line, audit_lines, format_report
from core.bill import normalize_item
from core.masking import contains_pii, mask_pii
from core.models import BillLine, Clause, JudgeOutput
from core.retrieve import RetrievedClause


class MaskingTest(unittest.TestCase):
    def test_masks_labelled_identifiers(self):
        text = "Patient Name: Ramesh Kumar\nUHID: SH2291447\nPolicy No: P/123/456"
        masked = mask_pii(text)
        for leaked in ("Ramesh", "SH2291447", "P/123/456"):
            self.assertNotIn(leaked, masked)

    def test_masks_phone_aadhaar_and_email(self):
        text = "Call 9876543210 or mail a@b.com. Aadhaar 1234 5678 9012."
        masked = mask_pii(text)
        self.assertNotIn("9876543210", masked)
        self.assertNotIn("a@b.com", masked)
        self.assertNotIn("1234 5678 9012", masked)
        self.assertFalse(contains_pii(masked))

    def test_leaves_clinical_content_alone(self):
        """Over-masking a drug name would change the verdict."""
        text = "Room Rent 8000 x 5 days = 40000\nInj Meropenem 1g\nSurgical Gloves 1200"
        masked = mask_pii(text)
        for kept in ("Room Rent", "Meropenem", "Surgical Gloves", "40000", "1200"):
            self.assertIn(kept, masked)

    def test_does_not_mask_dates_or_amounts(self):
        text = "Admission: 12/03/2026 Discharge: 17/03/2026 Total 240000.00"
        self.assertEqual(mask_pii(text), text)


class NormalizeTest(unittest.TestCase):
    def test_folds_case_and_whitespace(self):
        self.assertEqual(normalize_item("  Room   Rent (Single A/C)  "), "room rent (single a/c)")

    def test_is_idempotent(self):
        once = normalize_item("Surgical  Gloves")
        self.assertEqual(normalize_item(once), once)


def _candidate(clause_id="II.1", policy="star_health"):
    clause = Clause(
        clause_id=clause_id,
        title="In-patient Treatment",
        text="Room rent is limited to Rs 5,000 per day.",
        page=9,
        policy=policy,
        rule_type="room_rent",
    )
    return RetrievedClause(clause=clause, score=0.95, matched_text=clause.text)


class AuditLineTest(unittest.TestCase):
    def _run(self, judge_output, candidates=None, valid_ids=frozenset({"II.1"})):
        candidates = [_candidate()] if candidates is None else candidates
        with (
            mock.patch("core.audit.search", return_value=candidates),
            mock.patch("core.audit.complete_structured", return_value=judge_output),
        ):
            return audit_line(
                BillLine(item="room rent", amount=40000, qty=5),
                "star_health",
                500000,
                set(valid_ids),
            )

    def test_confident_verdict_is_computed_in_python(self):
        verdict = self._run(
            JudgeOutput(clause_id="II.1", limit_per_day=5000, confident=True, reasoning="capped")
        )
        self.assertEqual(verdict.allowed, 25000)
        self.assertEqual(verdict.clause_id, "II.1")
        self.assertTrue(verdict.over_limit)
        self.assertFalse(verdict.needs_human)

    def test_fabricated_clause_id_is_rejected(self):
        """The worst failure this system can produce - it must never pass."""
        verdict = self._run(
            JudgeOutput(clause_id="99.9", limit_per_day=5000, confident=True, reasoning="made up")
        )
        self.assertTrue(verdict.needs_human)
        self.assertIsNone(verdict.allowed)
        self.assertIsNone(verdict.clause_id, "an invented citation must not be reported")
        self.assertIn("does not exist", verdict.reason)

    def test_unconfident_judge_abstains(self):
        verdict = self._run(
            JudgeOutput(clause_id="II.1", confident=False, reasoning="nothing applies")
        )
        self.assertTrue(verdict.needs_human)
        self.assertIsNone(verdict.allowed)

    def test_nothing_retrieved_abstains(self):
        verdict = self._run(
            JudgeOutput(clause_id=None, confident=True, reasoning=""), candidates=[]
        )
        self.assertTrue(verdict.needs_human)
        self.assertIn("no policy clause", verdict.reason)

    def test_llm_failure_abstains_rather_than_guessing(self):
        from core.llm import LLMError

        with (
            mock.patch("core.audit.search", return_value=[_candidate()]),
            mock.patch("core.audit.complete_structured", side_effect=LLMError("ollama down")),
        ):
            verdict = audit_line(
                BillLine(item="room rent", amount=40000, qty=5), "star_health", 500000, {"II.1"}
            )
        self.assertTrue(verdict.needs_human)
        self.assertIsNone(verdict.allowed)


class AuditReportTest(unittest.TestCase):
    def test_totals_and_flag_count(self):
        lines = [
            BillLine(item="room rent", amount=40000, qty=5),
            BillLine(item="gloves", amount=1200, qty=1),
        ]
        outputs = [
            JudgeOutput(clause_id="II.1", limit_per_day=5000, confident=True, reasoning="a"),
            JudgeOutput(clause_id="II.1", confident=False, reasoning="b"),
        ]
        with (
            mock.patch("core.audit.load_clauses", return_value=[_candidate().clause]),
            mock.patch("core.audit.search", return_value=[_candidate()]),
            mock.patch("core.audit.complete_structured", side_effect=outputs),
        ):
            report = audit_lines(lines, "star_health", 500000)

        self.assertEqual(report.total_charged, 41200)
        self.assertEqual(report.total_allowed, 25000, "flagged lines contribute nothing")
        self.assertEqual(report.flagged_count, 1)
        self.assertEqual(report.policy, "star_health")

    def test_unknown_policy_is_rejected(self):
        with (
            mock.patch("core.audit.load_clauses", return_value=[]),
            self.assertRaises(ValueError),
        ):
            audit_lines([BillLine(item="x", amount=1)], "nonexistent", 500000)

    def test_report_renders(self):
        with (
            mock.patch("core.audit.load_clauses", return_value=[_candidate().clause]),
            mock.patch("core.audit.search", return_value=[_candidate()]),
            mock.patch(
                "core.audit.complete_structured",
                return_value=JudgeOutput(
                    clause_id="II.1", limit_per_day=5000, confident=True, reasoning="a"
                ),
            ),
        ):
            report = audit_lines(
                [BillLine(item="room rent", amount=40000, qty=5)], "star_health", 500000
            )
        text = format_report(report)
        self.assertIn("room rent", text)
        self.assertIn("TOTAL", text)


if __name__ == "__main__":
    unittest.main()
