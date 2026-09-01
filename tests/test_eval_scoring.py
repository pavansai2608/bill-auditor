"""PyUnit tests for the scorer itself, not the system it scores.

These exist because the fabricated-citation count - the project's central
claim, the metric that must stay at 0 - silently broke. The scorer built its
set of legitimate citations from `clauses.json` alone, so the 18 lines that
correctly cited `IRDAI-List-I` (which is exactly what the answer key cites for
those lines) were counted as inventions. Nothing failed; the number just went
wrong, in the direction that looks like the system misbehaving.

A metric that can break without anything failing needs a test holding it in
place.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import evaluate

from core.agent import IRDAI_CITATION
from core.models import AuditReport, LineVerdict


def expected_bill(clause_id: str) -> dict:
    return {
        "policy": "star_health",
        "sum_insured": 300000,
        "category": "non_payable",
        "lines": [
            {
                "item": "gloves",
                "charged": 500.0,
                "qty": 1,
                "allowed": 0.0,
                "clause_id": clause_id,
                "needs_human": False,
            }
        ],
    }


def report_citing(clause_id: str) -> AuditReport:
    verdict = LineVerdict(
        item="gloves",
        charged=500.0,
        allowed=0.0,
        clause_id=clause_id,
        reason="non-payable",
    )
    return AuditReport(
        lines=[verdict],
        total_charged=500.0,
        total_allowed=0.0,
        flagged_count=0,
        policy="star_health",
    )


def score(cited: str, valid_ids: set[str]) -> evaluate.Run:
    run = evaluate.Run()
    with mock.patch("core.audit.audit_lines", return_value=report_citing(cited)):
        evaluate.score_bill("B01", expected_bill(IRDAI_CITATION), valid_ids, run)
    return run


class CitableIdsTest(unittest.TestCase):
    def test_the_irdai_list_is_a_legitimate_citation(self):
        self.assertIn(IRDAI_CITATION, evaluate.citable_ids("star_health"))

    def test_policy_clauses_are_still_in_the_set(self):
        ids = evaluate.citable_ids("star_health")
        self.assertIn("II.1", ids)

    def test_another_policys_clause_is_not(self):
        # A citation from the wrong insurer is a fabricated citation.
        self.assertNotIn("B.1.1.1", evaluate.citable_ids("star_health"))

    def test_a_made_up_id_is_not(self):
        self.assertNotIn("II.999", evaluate.citable_ids("star_health"))


class FabricationCountTest(unittest.TestCase):
    def test_citing_the_irdai_list_is_not_a_fabrication(self):
        run = score(IRDAI_CITATION, evaluate.citable_ids("star_health"))
        self.assertEqual(run.overall.fabricated, 0)
        self.assertEqual(run.overall.citation_right, 1)

    def test_a_made_up_id_is_still_a_fabrication(self):
        run = score("II.999", evaluate.citable_ids("star_health"))
        self.assertEqual(run.overall.fabricated, 1)


class ToolCallCountTest(unittest.TestCase):
    """Both paths are counted, or an agent run reports 0.0 tool calls per bill."""

    def setUp(self):
        import core.agent as agent
        import core.audit as audit

        self.agent, self.audit = agent, audit
        self.before = (
            audit.search,
            audit.complete_structured,
            agent.search,
            agent.complete_structured,
        )
        # Stand in for the real ones, so the wrappers wrap a stub and no model
        # or vector store is reached.
        for mod in (audit, agent):
            mod.search = lambda *a, **k: []
            mod.complete_structured = lambda *a, **k: None

    def tearDown(self):
        (
            self.audit.search,
            self.audit.complete_structured,
            self.agent.search,
            self.agent.complete_structured,
        ) = self.before

    def test_calls_through_the_agent_module_are_counted(self):
        tally, restore = evaluate._calls()
        try:
            self.agent.search("q", "star_health")
            self.agent.complete_structured("prompt", None)
        finally:
            restore()
        self.assertEqual(tally, {"search": 1, "judge": 1})

    def test_calls_through_the_audit_module_are_counted(self):
        tally, restore = evaluate._calls()
        try:
            self.audit.search("q", "star_health")
        finally:
            restore()
        self.assertEqual(tally["search"], 1)

    def test_restore_puts_both_modules_back(self):
        stubs = (self.audit.search, self.agent.search)
        _, restore = evaluate._calls()
        self.assertNotEqual(self.audit.search, stubs[0])
        self.assertNotEqual(self.agent.search, stubs[1])
        restore()
        self.assertEqual((self.audit.search, self.agent.search), stubs)


if __name__ == "__main__":
    unittest.main()
