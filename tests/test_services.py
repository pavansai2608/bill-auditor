"""PyUnit tests for the six-container split.

The point of these is that splitting the monolith did not change any rule. The
audit logic is `core/`, imported by every service; what is tested here is the
wiring — that retrieval survives a round trip over HTTP unchanged, that the
gateway masks before anything crosses a network boundary, and that the
gateway's health tells the truth about its dependencies.
"""

import pathlib
import re
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from core.config import settings
from core.models import Clause
from core.retrieve import RetrievedClause
from services.audit import remote_retrieval

CLAUSE = Clause(
    clause_id="II.1",
    title="In-patient Treatment",
    text="Room rent up to 5,000 per day.",
    page=9,
    policy="star_health",
    rule_type="room_rent",
    refs=[],
)


class RetrievalServiceTest(unittest.TestCase):
    def setUp(self):
        from services.retrieval.main import app

        self.client = TestClient(app)

    def test_health_reports_the_clause_index(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertGreater(body["clauses"], 0)

    def test_search_returns_the_whole_clause_not_just_an_id(self):
        found = [RetrievedClause(clause=CLAUSE, score=0.93, matched_text="Room rent up to 5,000")]
        with mock.patch("services.retrieval.main.search", return_value=found) as search:
            body = self.client.post(
                "/search", json={"query": "room rent limit", "policy": "star_health"}
            ).json()

        search.assert_called_once()
        row = body["results"][0]
        self.assertEqual(row["clause"]["clause_id"], "II.1")
        self.assertEqual(row["score"], 0.93)
        # The judge reads matched_text, so it has to survive the hop.
        self.assertEqual(row["matched_text"], "Room rent up to 5,000")

    def test_a_bad_top_n_is_rejected(self):
        response = self.client.post(
            "/search", json={"query": "x", "policy": "star_health", "top_n": 99}
        )
        self.assertEqual(response.status_code, 422)


class RemoteRetrievalTest(unittest.TestCase):
    """A clause must come back from the service identical to a local one."""

    def test_the_round_trip_rebuilds_a_retrieved_clause(self):
        payload = {
            "results": [
                {
                    "clause": CLAUSE.model_dump(),
                    "score": 0.87,
                    "matched_text": "Room rent up to 5,000",
                    "via_ref_of": "II.28",
                }
            ]
        }
        response = mock.Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        http = mock.MagicMock()
        http.__enter__.return_value.post.return_value = response

        with (
            mock.patch.object(remote_retrieval.settings, "retrieval_url", "http://retrieval:8000"),
            mock.patch("services.audit.remote_retrieval.client", return_value=http),
        ):
            results = remote_retrieval.remote_search("room rent", "star_health", top_n=3)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], RetrievedClause)
        self.assertEqual(results[0].clause.clause_id, "II.1")
        self.assertEqual(results[0].via_ref_of, "II.28")

    def test_no_url_means_retrieval_stays_in_process(self):
        with mock.patch.object(remote_retrieval.settings, "retrieval_url", ""):
            self.assertFalse(remote_retrieval.install())

    def test_installing_patches_both_call_sites(self):
        import core.agent as agent
        import core.audit as audit

        before = (agent.search, audit.search)
        try:
            with mock.patch.object(remote_retrieval.settings, "retrieval_url", "http://r:8000"):
                self.assertTrue(remote_retrieval.install())
            # core.audit imports search into its own namespace too, so patching
            # only the agent would leave the naive path talking to a Chroma
            # collection the container does not have.
            self.assertIs(agent.search, remote_retrieval.remote_search)
            self.assertIs(audit.search, remote_retrieval.remote_search)
        finally:
            agent.search, audit.search = before


class GatewayTest(unittest.TestCase):
    def setUp(self):
        from services.gateway.main import app

        self.client = TestClient(app)

    def test_health_is_degraded_when_a_dependency_is_down(self):
        with mock.patch(
            "services.gateway.main.probe",
            side_effect=[
                {"service": "audit-service", "url": "x", "status": "ok"},
                {"service": "ingestion-service", "url": "y", "status": "unreachable"},
            ],
        ):
            body = self.client.get("/health").json()
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(len(body["dependencies"]), 2)

    def test_health_is_ok_when_everything_answers(self):
        with mock.patch(
            "services.gateway.main.probe",
            return_value={"service": "s", "url": "x", "status": "ok"},
        ):
            self.assertEqual(self.client.get("/health").json()["status"], "ok")

    def test_an_audit_is_forwarded_with_the_bill_already_masked(self):
        with mock.patch("services.gateway.main.forward", return_value={"job_id": "abc"}) as forward:
            response = self.client.post(
                "/audit",
                data={
                    "policy": "star_health",
                    "sum_insured": 300000,
                    "bill_text": "Patient Name: Ramesh Kumar\nRoom Rent 40000",
                },
            )

        self.assertEqual(response.status_code, 202)
        body = forward.call_args.kwargs["json"]
        self.assertNotIn("Ramesh Kumar", body["bill_text"])
        self.assertEqual(body["policy"], "star_health")

    def test_a_blank_room_limit_is_forwarded_as_blank(self):
        with mock.patch("services.gateway.main.forward", return_value={"job_id": "abc"}) as forward:
            self.client.post(
                "/audit",
                data={"policy": "star_health", "sum_insured": 300000, "bill_text": "x 100"},
            )
        body = forward.call_args.kwargs["json"]
        self.assertIsNone(body["room_limit_per_day"], "blank must not become a default")

    def test_an_unknown_policy_never_reaches_the_audit_service(self):
        with mock.patch("services.gateway.main.forward") as forward:
            response = self.client.post(
                "/audit", data={"policy": "acme", "sum_insured": 300000, "bill_text": "x 100"}
            )
        self.assertEqual(response.status_code, 404)
        forward.assert_not_called()

    def test_a_dead_inner_service_is_a_502_not_a_stack_trace(self):
        with mock.patch("services.gateway.main.client", side_effect=OSError("connection refused")):
            response = self.client.get("/audit/abc123")
        self.assertEqual(response.status_code, 502)
        self.assertIn("did not answer", response.json()["detail"])


class AuditServiceTest(unittest.TestCase):
    def setUp(self):
        from services.audit.main import app

        self.client = TestClient(app)

    def test_an_unknown_policy_is_rejected(self):
        response = self.client.post(
            "/audit", json={"bill_text": "x 100", "policy": "acme", "sum_insured": 300000}
        )
        self.assertEqual(response.status_code, 404)

    def test_a_bad_sum_insured_is_rejected_by_pydantic(self):
        response = self.client.post(
            "/audit", json={"bill_text": "x 100", "policy": "star_health", "sum_insured": 0}
        )
        self.assertEqual(response.status_code, 422)

    def test_health_names_the_model_and_whether_retrieval_is_remote(self):
        body = self.client.get("/health").json()
        self.assertIn("model", body)
        self.assertIn("remote_retrieval", body)

    def test_stats_says_whether_the_llm_cache_is_on(self):
        """A bill that is slow on every submission is usually this, not the key."""
        cache = self.client.get("/stats").json()["llm_cache"]
        self.assertIn("enabled", cache)
        self.assertIn("dir", cache)
        self.assertIn("entries", cache)


class IngestionServiceTest(unittest.TestCase):
    def setUp(self):
        from services.ingestion.main import app

        self.client = TestClient(app)

    def test_a_file_that_only_claims_to_be_a_pdf_is_rejected(self):
        response = self.client.post(
            "/policies/upload",
            files={"file": ("policy.pdf", b"not a pdf at all", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)

    def test_policies_are_listed_with_their_sums_insured(self):
        rows = self.client.get("/policies").json()
        self.assertTrue(any(row["id"] == "star_health" for row in rows))
        self.assertTrue(all("sum_insured_options" in row for row in rows))


if __name__ == "__main__":
    unittest.main()


class CompareProgressTest(unittest.TestCase):
    """What a compare job's `total` counts, pinned.

    A compare audits every line against every policy, so its total is line
    checks, not line items: a ten-line bill across three policies is 30. The UI
    once rendered that as "checked 0 of 30 lines" against a bill with ten
    items, which reads as a parser fault and is not one. The number is right;
    anything showing it has to say what it counts.
    """

    def test_the_total_is_lines_times_policies(self):
        from core.models import AuditReport, BillLine
        from services.audit import main as audit_main

        lines = [BillLine(item=f"item {n}", amount=1000.0) for n in range(10)]
        report = AuditReport(
            lines=[], total_charged=0.0, total_allowed=0.0, flagged_count=0, policy="star_health"
        )
        recorded: list[tuple[int, int | None]] = []

        with (
            mock.patch.object(audit_main, "known_policies", return_value=["a", "b", "c"]),
            mock.patch("core.bill.parse_bill", return_value=lines),
            mock.patch.object(audit_main, "audit_lines", return_value=report),
            mock.patch.object(audit_main.jobs, "start"),
            mock.patch.object(audit_main.jobs, "finish"),
            mock.patch.object(
                audit_main.jobs,
                "progress",
                side_effect=lambda _job, done, total=None: recorded.append((done, total)),
            ),
        ):
            audit_main.run_compare("job", audit_main.AuditRequest(bill_text="x", sum_insured=3e5))

        self.assertEqual(recorded[0], (0, 30))


class WarmUpGatesReadinessTest(unittest.TestCase):
    """A pod must not take traffic before its models are loaded.

    Measured cold on a laptop, loading bge-base and the cross-encoder takes
    44-74s. /health passes the moment uvicorn binds, so pointing a readiness
    probe at it routes the first real request into a minute of model loading -
    a production bug that looks like a slow bill.
    """

    def setUp(self):
        from services import common

        common._warm.update({"ready": False, "error": "", "seconds": 0.0})

    def test_ready_is_503_until_the_models_are_loaded(self):
        from services.retrieval.main import app

        client = TestClient(app)
        response = client.get("/ready")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ready"])

    def test_ready_is_200_once_warm(self):
        from services import common
        from services.retrieval.main import app

        common._warm.update({"ready": True, "seconds": 51.3})
        response = TestClient(app).get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["warm_seconds"], 51.3)

    def test_liveness_stays_green_while_warming(self):
        """Otherwise Kubernetes restarts the pod it is waiting for."""
        from services.retrieval.main import app

        self.assertEqual(TestClient(app).get("/health").status_code, 200)

    def test_a_failed_warm_up_is_reported_not_hidden(self):
        from services import common
        from services.retrieval.main import app

        common._warm.update({"ready": False, "error": "OSError: no such model"})
        body = TestClient(app).get("/ready").json()
        self.assertIn("no such model", body["error"])

    def test_warm_up_loads_the_reranker_only_where_it_is_used(self):
        """Ingestion embeds but never reranks, so it must not load one."""
        from services import common

        with (
            mock.patch("core.embeddings.get_embeddings") as embeddings,
            mock.patch("core.retrieve.get_cross_encoder") as reranker,
        ):
            common.warm_up(reranker=False)
            embeddings.assert_called_once()
            reranker.assert_not_called()

            common.warm_up(reranker=True)
            reranker.assert_called_once()


class BakedModelsMatchSettingsTest(unittest.TestCase):
    """The Dockerfiles name the model weights they download; config names the
    weights the code loads. They are two files and they can drift.

    Drift is silent in the worst way: the image would ship one model, the
    service would ask for another, and HF_HUB_OFFLINE=1 turns that into a
    container that will not start rather than a slow one. This is the check
    that makes it a test failure instead.

    The names are duplicated on purpose - copying core/ into the builder stage
    would make a one-character edit to any core module re-download 1.6 GB.
    """

    ROOT = pathlib.Path(__file__).resolve().parents[1]

    def _args(self, service: str) -> dict[str, str]:
        text = (self.ROOT / "services" / service / "Dockerfile").read_text()
        return dict(re.findall(r"^ARG (\w+)=(\S+)$", text, re.MULTILINE))

    def test_retrieval_bakes_both_models(self):
        args = self._args("retrieval")
        self.assertEqual(args.get("EMBEDDING_MODEL"), settings.embedding_model)
        self.assertEqual(args.get("RERANKER_MODEL"), settings.reranker_model)

    def test_ingestion_bakes_the_embedder_only(self):
        args = self._args("ingestion")
        self.assertEqual(args.get("EMBEDDING_MODEL"), settings.embedding_model)
        # Ingestion writes the index and never ranks a result. Baking the
        # cross-encoder here would be 550 MB this service cannot reach.
        self.assertNotIn("RERANKER_MODEL", args)

    def test_the_weights_are_never_fetched_at_runtime(self):
        """HF_HUB_OFFLINE is what makes the bake a guarantee.

        Without it a missing file degrades to a download - which is exactly the
        behaviour this change removed, and it would come back unnoticed because
        a warm developer machine has the cache and would never see it.
        """
        for service in ("retrieval", "ingestion"):
            text = (self.ROOT / "services" / service / "Dockerfile").read_text()
            with self.subTest(service=service):
                self.assertIn("HF_HUB_OFFLINE=1", text)
                self.assertIn("HF_HOME=/opt/hf", text)

    def test_the_start_period_no_longer_covers_a_download(self):
        """900s was sized for a cold download. A load from disk is ~60s."""
        for service in ("retrieval", "ingestion"):
            text = (self.ROOT / "services" / service / "Dockerfile").read_text()
            found = re.search(r"--start-period=(\d+)s", text)
            with self.subTest(service=service):
                self.assertIsNotNone(found)
                self.assertLessEqual(int(found.group(1)), 300)
