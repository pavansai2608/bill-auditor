"""PyUnit tests for the API. No model runs: the audit itself is stubbed.

What is tested here is the contract the frontend depends on - that a request
never blocks for 30-60 seconds, that a job id comes back immediately, that
polling reports honest progress, and that the finished report carries its
trace and its assumptions rather than a bare set of numbers.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from api.jobs import JobStore
from api.main import app
from core.assumptions import Assumptions
from core.models import AuditReport, BillLine, LineVerdict

client = TestClient(app)

BILL = "Room Rent 8,000 x 5 days  40000\nSurgeon Fee  80000"


def fake_report(policy="star_health", allowed=25000.0):
    assumptions = Assumptions()
    assumptions.note_differential_billing("II.1", "Proportionate deductions are not applied ...")
    return AuditReport(
        lines=[
            LineVerdict(
                item="room rent",
                charged=40000,
                allowed=allowed,
                clause_id="II.1",
                reason="II.1 table: 5,000 per day",
            )
        ],
        total_charged=40000,
        total_allowed=allowed,
        flagged_count=0,
        policy=policy,
        trace=[*assumptions.as_trace(), {"node": "summary", "item": "room rent", "attempts": 1}],
    )


def stub_audit(*args, **kwargs):
    policy = args[1] if len(args) > 1 else kwargs["policy"]
    on_progress = kwargs.get("on_progress")
    if on_progress:
        on_progress(1, 1)
    return fake_report(policy)


def stubbed():
    """Patch out the two things that would reach the model."""
    return (
        mock.patch(
            "core.bill.parse_bill", return_value=[BillLine(item="room rent", amount=40000, qty=5)]
        ),
        mock.patch("api.main.audit_lines", side_effect=stub_audit),
    )


class MetaTest(unittest.TestCase):
    def test_health_reports_the_clause_index(self):
        body = client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertGreater(body["clauses"], 0)
        self.assertIn("star_health", body["policies"])

    def test_health_says_whether_a_repeat_audit_can_be_answered_from_disk(self):
        """Without this, a cache switched off for a timing run is invisible."""
        body = client.get("/health").json()
        self.assertIn("enabled", body["llm_cache"])
        self.assertIn("dir", body["llm_cache"])
        self.assertIn(body["backend"], {"ollama", "groq"})

    def test_policies_lists_the_dropdown(self):
        body = client.get("/policies").json()
        ids = {row["id"] for row in body}
        self.assertEqual(ids, {"star_health", "hdfc_ergo", "niva_bupa"})
        names = {row["id"]: row["name"] for row in body}
        self.assertEqual(names["star_health"], "Star Health")
        self.assertEqual(names["hdfc_ergo"], "HDFC ERGO", "not 'Hdfc Ergo'")
        star = next(row for row in body if row["id"] == "star_health")
        self.assertGreater(star["clauses"], 0)

    def test_policies_carry_the_sums_insured_they_support(self):
        body = client.get("/policies").json()
        options = {row["id"]: row["sum_insured_options"] for row in body}
        # star_health prices its room limit by sum insured, so its dropdown is
        # its own table rather than a guessed list.
        self.assertIn(300000, options["star_health"])
        self.assertIn(2500000, options["star_health"])
        self.assertEqual(options["hdfc_ergo"], [300000, 500000, 1000000, 2500000])

    def test_the_docs_page_renders(self):
        self.assertEqual(client.get("/docs").status_code, 200)
        self.assertIn("/audit", client.get("/openapi.json").json()["paths"])


class AuditTest(unittest.TestCase):
    def post(self, **overrides):
        data = {"policy": "star_health", "sum_insured": 300000, "bill_text": BILL}
        data.update(overrides)
        return client.post("/audit", data=data)

    def test_the_request_returns_a_job_id_immediately(self):
        parse, audit = stubbed()
        with parse, audit:
            response = self.post()
        self.assertEqual(response.status_code, 202)
        self.assertIn("job_id", response.json())

    def test_polling_returns_the_report_with_its_trace_and_assumptions(self):
        parse, audit = stubbed()
        with parse, audit:
            job_id = self.post().json()["job_id"]
            body = client.get(f"/audit/{job_id}").json()

        self.assertEqual(body["status"], "done")
        report = body["report"]
        self.assertEqual(report["total_allowed"], 25000.0)
        self.assertEqual(report["lines"][0]["clause_id"], "II.1")
        self.assertTrue(report["trace"], "the trace must reach the client")
        self.assertTrue(report["assumptions"], "the ASSUMPTIONS block must reach the client")
        self.assertIn("differential billing", report["assumptions"][0]["statement"])

    def test_the_optional_schedule_inputs_are_passed_through(self):
        parse, audit = stubbed()
        with parse, audit as audit_mock:
            self.post(room_limit_per_day=5000)
        schedule = audit_mock.call_args.args[3]
        self.assertEqual(schedule.room_limit_per_day, 5000)

    def test_a_blank_schedule_stays_blank(self):
        parse, audit = stubbed()
        with parse, audit as audit_mock:
            self.post()
        self.assertIsNone(audit_mock.call_args.args[3], "blank must not become a default")

    def test_the_dates_are_passed_through(self):
        parse, audit = stubbed()
        with parse, audit as audit_mock:
            self.post(policy_start_date="2025-10-01", admission_date="2026-02-14")
        self.assertEqual(audit_mock.call_args.kwargs["policy_start_date"], "2025-10-01")
        self.assertEqual(audit_mock.call_args.kwargs["admission_date"], "2026-02-14")

    def test_an_uploaded_text_bill_is_accepted(self):
        parse, audit = stubbed()
        with parse, audit:
            response = client.post(
                "/audit",
                data={"policy": "star_health", "sum_insured": 300000},
                files={"bill": ("bill.txt", BILL.encode(), "text/plain")},
            )
        self.assertEqual(response.status_code, 202)

    def test_an_unknown_policy_is_rejected(self):
        self.assertEqual(self.post(policy="acme_health").status_code, 404)

    def test_a_missing_bill_is_rejected(self):
        response = client.post("/audit", data={"policy": "star_health", "sum_insured": 300000})
        self.assertEqual(response.status_code, 400)

    def test_a_pdf_bill_is_refused_clearly(self):
        response = client.post(
            "/audit",
            data={"policy": "star_health", "sum_insured": 300000},
            files={"bill": ("bill.pdf", b"%PDF-1.7 binary", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])

    def test_a_bad_sum_insured_is_rejected_by_pydantic(self):
        response = client.post(
            "/audit", data={"policy": "star_health", "sum_insured": -5, "bill_text": BILL}
        )
        self.assertEqual(response.status_code, 422)

    def test_a_non_numeric_sum_insured_is_rejected_by_pydantic(self):
        response = client.post(
            "/audit", data={"policy": "star_health", "sum_insured": "lots", "bill_text": BILL}
        )
        self.assertEqual(response.status_code, 422)

    def test_the_bill_is_masked_before_it_reaches_the_job(self):
        """PII never enters the job store, which outlives the request."""
        seen = {}

        def capture(text, *args, **kwargs):
            seen["text"] = text
            return [BillLine(item="room rent", amount=40000, qty=5)]

        with (
            mock.patch("core.bill.parse_bill", side_effect=capture),
            mock.patch("api.main.audit_lines", side_effect=stub_audit),
        ):
            self.post(bill_text="Patient Name: Ramesh Kumar\nPhone: 9876543210\n" + BILL)

        self.assertNotIn("Ramesh Kumar", seen["text"])
        self.assertNotIn("9876543210", seen["text"])
        self.assertIn("REDACTED", seen["text"])

    def test_a_job_is_polled_from_running_to_done(self):
        """The shape the frontend switches on, observed mid-flight."""
        from api.jobs import jobs as store
        from api.main import run_audit

        observed = []

        def audit_with_a_look_at_the_job(*args, **kwargs):
            job_id = kwargs["_job_id"] if "_job_id" in kwargs else observed_job[0]
            on_progress = kwargs["on_progress"]
            on_progress(1, 3)
            observed.append(store.get(job_id).as_status())
            on_progress(3, 3)
            return fake_report()

        job = store.create("audit")
        observed_job = [job.job_id]
        with (
            mock.patch(
                "core.bill.parse_bill",
                return_value=[BillLine(item="room rent", amount=40000, qty=5)],
            ),
            mock.patch("api.main.audit_lines", side_effect=audit_with_a_look_at_the_job),
        ):
            run_audit(
                job.job_id,
                BILL,
                "star_health",
                {
                    "sum_insured": 300000,
                    "schedule": None,
                    "policy_start_date": None,
                    "admission_date": None,
                    "differential_billing": True,
                },
            )

        self.assertEqual(observed[0]["status"], "running")
        self.assertEqual((observed[0]["done"], observed[0]["total"]), (1, 3))
        finished = store.get(job.job_id).as_status()
        self.assertEqual(finished["status"], "done")
        self.assertEqual(finished["report"]["total_allowed"], 25000.0)

    def test_an_unknown_job_is_a_404(self):
        self.assertEqual(client.get("/audit/nosuchjob").status_code, 404)

    def test_a_failing_audit_is_reported_as_failed_not_as_a_500(self):
        parse = mock.patch("core.bill.parse_bill", side_effect=RuntimeError("ollama is down"))
        with parse:
            job_id = self.post().json()["job_id"]
        body = client.get(f"/audit/{job_id}").json()
        self.assertEqual(body["status"], "failed")
        self.assertIn("ollama is down", body["error"])


class CompareTest(unittest.TestCase):
    def test_one_bill_against_every_policy(self):
        parse, audit = stubbed()
        with parse, audit:
            job_id = client.post(
                "/compare", data={"sum_insured": 300000, "bill_text": BILL}
            ).json()["job_id"]
            body = client.get(f"/compare/{job_id}").json()

        self.assertEqual(body["status"], "done")
        self.assertEqual(len(body["report"]["reports"]), 3)
        self.assertIn(body["report"]["best_policy"], {"star_health", "hdfc_ergo", "niva_bupa"})
        self.assertEqual(body["report"]["difference"], 0.0)

    def test_an_audit_job_is_not_a_compare_job(self):
        parse, audit = stubbed()
        with parse, audit:
            job_id = client.post(
                "/audit", data={"policy": "star_health", "sum_insured": 300000, "bill_text": BILL}
            ).json()["job_id"]
        self.assertEqual(client.get(f"/compare/{job_id}").status_code, 404)


class UploadTest(unittest.TestCase):
    def test_a_pdf_is_stored_and_indexed_as_a_job(self):
        from core.config import settings

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(
                type(settings),
                "policies_dir",
                new_callable=mock.PropertyMock,
                return_value=Path(tmp),
            ),
            mock.patch("core.ingest.run") as ingest,
        ):
            ingest.return_value = [mock.Mock(policy="my_policy"), mock.Mock(policy="star_health")]
            response = client.post(
                "/policies/upload",
                files={"file": ("My Policy.pdf", b"%PDF-1.7 fake", "application/pdf")},
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["policy"], "my_policy")
            # The name is rebuilt from scratch, so an upload cannot write
            # outside the policies directory.
            self.assertTrue((Path(tmp) / "my_policy.pdf").exists())
            body = client.get(f"/jobs/{response.json()['job_id']}").json()
            self.assertEqual(body["status"], "done")
            self.assertEqual(body["report"]["clauses"], 1)

    def test_a_non_pdf_is_rejected(self):
        response = client.post(
            "/policies/upload", files={"file": ("policy.txt", b"not a pdf", "text/plain")}
        )
        self.assertEqual(response.status_code, 400)

    def test_a_file_that_only_claims_to_be_a_pdf_is_rejected(self):
        response = client.post(
            "/policies/upload",
            files={"file": ("policy.pdf", b"still not a pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)


class JobStoreTest(unittest.TestCase):
    """The polling shapes the frontend switches on."""

    def test_a_running_job_reports_progress(self):
        store = JobStore()
        job = store.create("audit")
        store.start(job.job_id)
        store.progress(job.job_id, 3, 7)
        self.assertEqual(
            store.get(job.job_id).as_status(),
            {"job_id": job.job_id, "status": "running", "done": 3, "total": 7},
        )

    def test_a_finished_job_reports_the_report(self):
        store = JobStore()
        job = store.create("audit", total=7)
        store.finish(job.job_id, {"total_allowed": 1})
        status = store.get(job.job_id).as_status()
        self.assertEqual(status["status"], "done")
        self.assertEqual(status["report"], {"total_allowed": 1})
        self.assertNotIn("done", status, "a finished job reports a report, not a counter")

    def test_a_failed_job_reports_the_error(self):
        store = JobStore()
        job = store.create("audit")
        store.fail(job.job_id, "ollama is down")
        self.assertEqual(store.get(job.job_id).as_status()["error"], "ollama is down")

    def test_the_default_cap_is_a_hundred_jobs(self):
        from core.config import settings

        self.assertEqual(settings.max_jobs_kept, 100)

    def test_old_jobs_are_dropped_rather_than_growing_without_bound(self):
        store = JobStore(keep=3)
        ids = [store.create("audit").job_id for _ in range(5)]
        self.assertIsNone(store.get(ids[0]))
        self.assertIsNotNone(store.get(ids[-1]))


if __name__ == "__main__":
    unittest.main()
