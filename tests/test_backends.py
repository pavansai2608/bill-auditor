"""The two backends, and the four promises that make a hosted one acceptable.

Nothing here touches the network. Every Groq call is a stub, which is also the
point of the last test: the suite defaults to ollama and must never make a real
call to anything.
"""

import time
import unittest
from unittest import mock

from core import backends, llm
from core.assumptions import LLM_FALLBACK, Assumptions
from core.backends import GROQ, OLLAMA, GroqLimiter, PIIWouldLeave, QuotaExhausted, TokenBucket
from core.config import settings


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class RateLimited(Exception):
    """What langchain-groq raises on a 429, near enough."""

    def __init__(self, message: str = "Error code: 429 - rate limit reached") -> None:
        super().__init__(message)


class ContextDefaultsTest(unittest.TestCase):
    """Where each default comes from, and that one override beats all of them."""

    def test_the_api_defaults_to_groq_and_the_eval_to_ollama(self):
        self.assertEqual(settings.backend_for("api"), GROQ)
        self.assertEqual(settings.backend_for("eval"), OLLAMA)

    def test_the_cli_and_anything_unnamed_default_to_ollama(self):
        self.assertEqual(settings.backend_for("cli"), OLLAMA)
        self.assertEqual(settings.backend_for("test"), OLLAMA)

    def test_an_explicit_backend_wins_everywhere(self):
        """This is what lets docker and k8s choose with no code change."""
        with mock.patch.object(settings, "llm_backend", GROQ):
            for context in ("api", "eval", "cli", "anything"):
                with self.subTest(context=context):
                    self.assertEqual(settings.backend_for(context), GROQ)

    def test_the_tests_themselves_are_on_ollama(self):
        self.assertEqual(llm.active_backend(), OLLAMA)


class TokenBucketTest(unittest.TestCase):
    """The limiter counts tokens, because that is the cap that binds first."""

    def test_it_hands_out_what_it_has_without_waiting(self):
        bucket = TokenBucket(capacity=6000, per_second=100)
        self.assertEqual(bucket.take(6000), 0.0)

    def test_it_waits_once_the_bucket_is_empty(self):
        bucket = TokenBucket(capacity=100, per_second=100)
        bucket.take(100)
        started = time.monotonic()
        bucket.take(50)
        self.assertGreater(time.monotonic() - started, 0.2)

    def test_a_wait_longer_than_the_deadline_is_an_error_not_a_hang(self):
        bucket = TokenBucket(capacity=6000, per_second=1)
        bucket.take(6000)
        with self.assertRaises(backends.BackendError):
            bucket.take(6000, timeout_s=0.1)

    def test_the_estimate_scales_with_content_and_errs_high(self):
        """It should over-estimate: a low guess costs a 429, a high one costs
        a little throughput."""
        text = "word " * 500  # 2,500 characters, ~625 real tokens
        estimate = backends.estimate_tokens([FakeMessage(text)])
        self.assertGreater(estimate, 625, "an under-estimate collects 429s")
        self.assertLess(estimate, 625 * 2, "wildly high would throttle for nothing")

        # Twice the text, near enough twice the estimate.
        doubled = backends.estimate_tokens([FakeMessage(text * 2)])
        self.assertAlmostEqual(doubled / estimate, 2.0, delta=0.2)


class DailyQuotaTest(unittest.TestCase):
    def limiter(self, cap: int = 2) -> GroqLimiter:
        return GroqLimiter(
            tokens=TokenBucket(capacity=10_000, per_second=10_000),
            requests=TokenBucket(capacity=100, per_second=100),
            daily_cap=cap,
        )

    def test_the_day_runs_out_and_says_so(self):
        limiter = self.limiter(cap=2)
        limiter.acquire(10)
        limiter.acquire(10)
        with self.assertRaises(QuotaExhausted):
            limiter.acquire(10)

    def test_groqs_own_word_beats_our_count(self):
        limiter = self.limiter(cap=100)
        limiter.note_quota_exhausted()
        with self.assertRaises(QuotaExhausted):
            limiter.acquire(10)


class BackoffAndFallbackTest(unittest.TestCase):
    """A 429 is waited out. A spent day is handed to the local model."""

    def setUp(self):
        llm.reset_client()
        backends.reset_clients()
        self.addCleanup(llm.reset_client)
        self.addCleanup(backends.reset_clients)

    def test_a_429_backs_off_and_retries(self):
        attempts = []

        class Flaky:
            def invoke(self, messages):
                attempts.append(time.monotonic())
                if len(attempts) < 3:
                    raise RateLimited()
                return "answered"

        with (
            mock.patch.object(backends, "client", return_value=Flaky()),
            mock.patch.object(settings, "groq_backoff_base_s", 0.01),
            mock.patch.object(time, "sleep") as slept,
        ):
            result = backends.invoke(GROQ, [FakeMessage("clean text")])

        self.assertEqual(result, "answered")
        self.assertEqual(len(attempts), 3)
        # Exponential, not flat: each wait is longer than the one before.
        waits = [call.args[0] for call in slept.call_args_list]
        self.assertEqual(len(waits), 2)
        self.assertGreater(waits[1], waits[0])

    def test_it_gives_up_after_the_configured_number_of_tries(self):
        class Always:
            def invoke(self, messages):
                raise RateLimited()

        with (
            mock.patch.object(backends, "client", return_value=Always()),
            mock.patch.object(settings, "groq_max_retries", 2),
            mock.patch.object(settings, "groq_backoff_base_s", 0.01),
            mock.patch.object(time, "sleep"),
            self.assertRaises(backends.BackendError),
        ):
            backends.invoke(GROQ, [FakeMessage("clean text")])

    def test_a_daily_quota_error_is_not_retried_it_is_raised_to_fall_back(self):
        calls = []

        class Spent:
            def invoke(self, messages):
                calls.append(1)
                raise RateLimited("Error code: 429 - rate limit reached for requests per day")

        with (
            mock.patch.object(backends, "client", return_value=Spent()),
            mock.patch.object(time, "sleep"),
            self.assertRaises(QuotaExhausted),
        ):
            backends.invoke(GROQ, [FakeMessage("clean text")])

        self.assertEqual(len(calls), 1, "a spent day is not worth retrying")

    def test_an_exhausted_quota_falls_back_to_ollama_and_is_recorded(self):
        """The promise: never a half-finished audit because a free tier ran out."""
        seen = []

        def fake_invoke(backend, messages, structured=None):
            seen.append(backend)
            if backend == GROQ:
                raise QuotaExhausted("groq daily quota is used up for today")
            return "from ollama"

        llm.use_backend(GROQ)
        with mock.patch.object(backends, "invoke", side_effect=fake_invoke):
            result = llm._invoke([FakeMessage("clean text")])

        self.assertEqual(result, "from ollama")
        self.assertEqual(seen, [GROQ, OLLAMA])
        self.assertTrue(llm.FELL_BACK["happened"])
        # The fallback is for this call. The process stays configured for Groq
        # and returns to it when the cooldown expires. This assertion used to
        # read OLLAMA, pinning a permanent switch - which is exactly the defect
        # it turned out to be: one refused call degraded the container for its
        # whole life, and nothing reported it.
        self.assertEqual(llm.active_backend(), GROQ, "the process is not switched")
        self.assertTrue(llm.groq_is_down(), "but groq is skipped until the cooldown ends")

    def test_the_cooldown_stops_every_line_paying_for_a_refusal(self):
        """One refusal, then straight to Ollama - no second round trip."""
        seen = []

        def fake_invoke(backend, messages, structured=None):
            seen.append(backend)
            if backend == GROQ:
                raise QuotaExhausted("groq daily quota is used up for today")
            return "from ollama"

        llm.use_backend(GROQ)
        with mock.patch.object(backends, "invoke", side_effect=fake_invoke):
            for _ in range(4):
                llm._invoke([FakeMessage("clean text")])

        # Groq is tried once, not four times. Without the cooldown every line
        # of a ten-line bill spends a failed call to learn what line one knew.
        self.assertEqual(seen.count(GROQ), 1)
        self.assertEqual(seen.count(OLLAMA), 4)

    def test_the_cooldown_expires_so_the_process_recovers(self):
        """A quota window reopens. Nothing should need a restart to notice."""
        seen = []

        def fake_invoke(backend, messages, structured=None):
            seen.append(backend)
            if backend == GROQ and len(seen) == 1:
                raise QuotaExhausted("groq daily quota is used up for today")
            return "ok"

        llm.use_backend(GROQ)
        self.addCleanup(setattr, settings, "groq_cooldown_s", settings.groq_cooldown_s)
        settings.groq_cooldown_s = 0.05
        with mock.patch.object(backends, "invoke", side_effect=fake_invoke):
            llm._invoke([FakeMessage("clean text")])
            self.assertTrue(llm.groq_is_down())
            time.sleep(0.06)
            self.assertFalse(llm.groq_is_down())
            llm._invoke([FakeMessage("clean text")])

        self.assertEqual(seen, [GROQ, OLLAMA, GROQ])

    def test_the_fallback_reaches_the_report_as_an_assumption(self):
        assumptions = Assumptions()
        assumptions.note_llm_fallback("groq daily quota is used up for today")
        entry = assumptions.as_trace()[-1]
        self.assertEqual(entry["assumption"], LLM_FALLBACK)
        self.assertIn("local model", entry["statement"])


class NothingIdentifyingLeavesTest(unittest.TestCase):
    """The guarantee that makes a hosted backend acceptable at all.

    Masking runs at intake, before parsing, so this should never fire. It is
    here because "should never" and "cannot" are different promises, and only
    one of them holds when the text is about to cross a network.
    """

    def test_a_phone_number_is_refused(self):
        with self.assertRaises(PIIWouldLeave):
            backends.guard_pii([FakeMessage("Patient contact 9876543210")])

    def test_an_aadhaar_number_is_refused(self):
        with self.assertRaises(PIIWouldLeave):
            backends.guard_pii([FakeMessage("ID 1234 5678 9012")])

    def test_an_email_is_refused(self):
        with self.assertRaises(PIIWouldLeave):
            backends.guard_pii([FakeMessage("write to ramesh@example.com")])

    def test_a_masked_bill_passes(self):
        from core.masking import mask_pii

        raw = "Patient Name: Ramesh Kumar\nPhone: 9876543210\nRoom Rent 8,000 x 5   40000"
        backends.guard_pii([FakeMessage(mask_pii(raw))])

    def test_the_groq_client_is_never_reached_with_unmasked_text(self):
        """The guard fires before the client is built, let alone called."""
        client = mock.Mock()
        with (
            mock.patch.object(backends, "client", return_value=client),
            self.assertRaises(PIIWouldLeave),
        ):
            backends.invoke(GROQ, [FakeMessage("Phone: 9876543210")])
        client.invoke.assert_not_called()

    def test_ollama_is_not_subject_to_the_guard(self):
        """A local model never sends anything anywhere; the risk is not the same."""
        client = mock.Mock()
        client.invoke.return_value = "fine"
        with mock.patch.object(backends, "client", return_value=client):
            self.assertEqual(backends.invoke(OLLAMA, [FakeMessage("Phone: 9876543210")]), "fine")


class CacheIsKeyedByBackendTest(unittest.TestCase):
    """A Qwen answer must never come back wearing Llama's name."""

    def setUp(self):
        llm.reset_client()
        self.addCleanup(llm.reset_client)

    def test_the_same_prompt_keys_differently_per_backend(self):
        messages = llm._build_messages("what is the room rent limit?", system=None)

        llm.use_backend(OLLAMA)
        ollama_key = llm.cache_key(messages, schema_name="JudgeOutput")
        llm.use_backend(GROQ)
        groq_key = llm.cache_key(messages, schema_name="JudgeOutput")

        self.assertNotEqual(ollama_key, groq_key)

    def test_the_model_name_is_in_the_key_too(self):
        messages = llm._build_messages("same prompt", system=None)
        llm.use_backend(GROQ)
        before = llm.cache_key(messages, schema_name=None)
        with mock.patch.object(settings, "groq_model", "llama-3.1-8b-instant"):
            after = llm.cache_key(messages, schema_name=None)
        self.assertNotEqual(before, after)


class UnknownBackendTest(unittest.TestCase):
    def test_a_typo_is_refused_rather_than_defaulted(self):
        with self.assertRaises(backends.BackendError):
            backends.client("gpt4")
        with self.assertRaises(backends.BackendError):
            llm.use_backend("gorq")


if __name__ == "__main__":
    unittest.main()


class PermanentErrorsFailFastTest(unittest.TestCase):
    """A wrong model name is a configuration mistake, not a transient failure.

    It was retried three times a line, each attempt first waiting on the token
    bucket, so a one-word typo became a twenty-minute run that failed anyway.
    """

    def test_a_retired_model_id_is_raised_at_once(self):
        calls = []

        class Missing:
            def invoke(self, messages):
                calls.append(1)
                raise RuntimeError(
                    "Error code: 404 - {'error': {'message': 'The model "
                    "`llama-3.3-70b-versatile` does not exist or you do not have "
                    "access to it.', 'code': 'model_not_found'}}"
                )

        with (
            mock.patch.object(backends, "client", return_value=Missing()),
            self.assertRaises(backends.BackendError),
        ):
            backends.invoke(GROQ, [FakeMessage("clean text")])

        self.assertEqual(len(calls), 1, "a retired model id will not fix itself")

    def test_a_bad_key_is_raised_at_once(self):
        class Rejected:
            def invoke(self, messages):
                raise RuntimeError("Error code: 401 - invalid_api_key")

        with (
            mock.patch.object(backends, "client", return_value=Rejected()),
            self.assertRaises(backends.BackendError),
        ):
            backends.invoke(GROQ, [FakeMessage("clean text")])

    def test_a_429_is_still_retried(self):
        """The fast path must not swallow the case backoff exists for."""
        self.assertFalse(backends.is_permanent(RateLimited()))
        self.assertTrue(backends.is_rate_limited(RateLimited()))


class BadWifiTest(unittest.TestCase):
    """The demo case: the venue's network is gone, the laptop's model is not.

    Groq failing on the network used to crash the audit, because only an
    exhausted quota triggered the fallback. A dead connection is the more
    likely of the two in a room full of people.
    """

    def setUp(self):
        llm.reset_client()
        backends.reset_clients()
        self.addCleanup(llm.reset_client)
        self.addCleanup(backends.reset_clients)

    def test_a_connection_failure_is_recognised(self):
        for error in (
            ConnectionError("connection refused"),
            RuntimeError("APIConnectionError: Connection error."),
            RuntimeError("Error code: 503 - service unavailable"),
            RuntimeError("Temporary failure in name resolution"),
        ):
            with self.subTest(error=str(error)[:30]):
                self.assertTrue(backends.is_unreachable(error))

    def test_it_is_not_confused_with_a_rate_limit_or_a_bad_model(self):
        self.assertFalse(backends.is_unreachable(RateLimited()))
        self.assertFalse(backends.is_unreachable(RuntimeError("404 model_not_found")))

    def test_the_audit_finishes_on_ollama_when_the_network_dies(self):
        seen = []

        def fake_invoke(backend, messages, structured=None):
            seen.append(backend)
            if backend == GROQ:
                raise backends.Unreachable("APIConnectionError: Connection error.")
            return "finished locally"

        llm.use_backend(GROQ)
        with mock.patch.object(backends, "invoke", side_effect=fake_invoke):
            result = llm._invoke([FakeMessage("clean text")])

        self.assertEqual(result, "finished locally")
        self.assertEqual(seen, [GROQ, OLLAMA])
        self.assertTrue(llm.FELL_BACK["happened"])
        self.assertEqual(llm.active_backend(), GROQ, "bad wifi does not reconfigure the process")
        self.assertTrue(llm.groq_is_down())
