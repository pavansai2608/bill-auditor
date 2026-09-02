"""The two LLM backends, and the rules that separate them.

    ollama  local Qwen3 8B. ~11s a line, no rate limit, works offline.
    groq    hosted Llama 3.3 70B. ~1s a call, hard free-tier limits.

They are not interchangeable and the code should not pretend they are. Ollama
is the one that can absorb a 400-call evaluation; Groq is the one that answers
while somebody is watching. Which is used where is decided in `core.config`
(`backend_for`), never at a call site.

What is identical, deliberately: both go through LangChain's
`with_structured_output`, so `JudgeOutput` is parsed the same way on both, and
any parsing that works for one and not the other is a bug rather than a
difference of backend.

Three things this module owns beyond building a client:

- **A token bucket, counted in tokens, not requests.** Groq's free tier is
  6,000 tokens a minute against 30 requests a minute, and a judge call carries
  a policy clause. The token cap binds first, every time; a request-counting
  limiter would sail past it and collect 429s.
- **Exponential backoff on 429**, honouring `retry-after` when Groq sends one.
- **Automatic fallback to Ollama when the daily quota is gone.** A person
  should not be shown a half-finished audit because a free tier ran out at
  line seven. The fallback is recorded, not silent: it is logged and it shows
  up in the report's assumptions block.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.config import settings
from core.logging_conf import get_logger
from core.masking import contains_pii

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

log = get_logger(__name__)

OLLAMA = "ollama"
GROQ = "groq"
BACKENDS = (OLLAMA, GROQ)


class BackendError(RuntimeError):
    """The backend cannot serve this call at all."""


class QuotaExhausted(BackendError):
    """The daily allowance is gone. The caller should fall back."""


class PIIWouldLeave(BackendError):
    """Refused: this text still has an identifier in it.

    Only raised on the hosted path. Masking already happens before parsing, so
    reaching here means something bypassed it - and the difference between a
    local model and a hosted one is that a mistake here leaves the machine.
    """


# --------------------------------------------------------------------------
# rate limiting
# --------------------------------------------------------------------------


@dataclass
class TokenBucket:
    """Tokens per minute, refilled continuously rather than in steps.

    A minute-boundary counter lets a burst through at 59s and again at 61s,
    which is exactly how a free tier gets exhausted in two seconds. This
    refills at capacity/60 per second, so the average is what it says.
    """

    capacity: int
    per_second: float
    available: float = field(init=False)
    updated: float = field(init=False)
    _lock: threading.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.available = float(self.capacity)
        self.updated = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self, now: float) -> None:
        self.available = min(
            float(self.capacity), self.available + (now - self.updated) * self.per_second
        )
        self.updated = now

    def take(self, tokens: float, *, timeout_s: float = 120.0) -> float:
        """Wait until `tokens` are available, then spend them.

        Returns how long it waited, so a caller can log a limiter that is
        actually biting rather than guessing.
        """
        wanted = min(float(tokens), float(self.capacity))
        waited = 0.0
        deadline = time.monotonic() + timeout_s

        while True:
            with self._lock:
                now = time.monotonic()
                self._refill(now)
                if self.available >= wanted:
                    self.available -= wanted
                    return waited
                short = wanted - self.available
                sleep_for = short / self.per_second

            if time.monotonic() + sleep_for > deadline:
                raise BackendError(
                    f"rate limiter would wait {sleep_for:.0f}s for {wanted:.0f} tokens, "
                    f"which is longer than the {timeout_s:.0f}s allowed"
                )
            time.sleep(min(sleep_for, 1.0))
            waited += min(sleep_for, 1.0)


def estimate_tokens(messages: list[Any]) -> int:
    """Roughly four characters a token, plus per-message overhead.

    Deliberately an over-estimate. Guessing high costs a little throughput;
    guessing low costs a 429 and a backoff, which is slower.
    """
    characters = sum(len(str(getattr(m, "content", m))) for m in messages)
    return int(characters / 3.5) + 16 * len(messages) + 64


@dataclass
class GroqLimiter:
    """Everything the free tier counts, in one place."""

    tokens: TokenBucket
    requests: TokenBucket
    daily_cap: int
    used_today: int = 0
    day: float = field(default_factory=lambda: time.time() // 86400)

    @classmethod
    def from_settings(cls) -> GroqLimiter:
        return cls(
            tokens=TokenBucket(
                capacity=settings.groq_tokens_per_minute,
                per_second=settings.groq_tokens_per_minute / 60,
            ),
            requests=TokenBucket(
                capacity=settings.groq_requests_per_minute,
                per_second=settings.groq_requests_per_minute / 60,
            ),
            daily_cap=settings.groq_requests_per_day,
        )

    def _roll_day(self) -> None:
        today = time.time() // 86400
        if today != self.day:
            self.day = today
            self.used_today = 0

    def acquire(self, token_estimate: int) -> None:
        """Block until this call is allowed, or say the day is over."""
        self._roll_day()
        if self.used_today >= self.daily_cap:
            raise QuotaExhausted(
                f"groq daily quota of {self.daily_cap} requests is used up for today"
            )
        waited = self.tokens.take(token_estimate)
        waited += self.requests.take(1)
        if waited > 1.0:
            log.info("groq rate limiter waited %.1fs for %d tokens", waited, token_estimate)
        self.used_today += 1

    def note_quota_exhausted(self) -> None:
        """Groq itself said the day is over; believe it over our own count."""
        self.used_today = self.daily_cap


_limiter: GroqLimiter | None = None


def limiter() -> GroqLimiter:
    global _limiter
    if _limiter is None:
        _limiter = GroqLimiter.from_settings()
    return _limiter


def reset_limiter() -> None:
    """Tests, and anything that changes the settings."""
    global _limiter
    _limiter = None


# --------------------------------------------------------------------------
# clients
# --------------------------------------------------------------------------

_clients: dict[str, Any] = {}


def build_ollama() -> BaseChatModel:
    from langchain_ollama import ChatOllama

    log.info(
        "connecting to ollama model=%s num_ctx=%d url=%s",
        settings.ollama_model,
        settings.num_ctx,
        settings.ollama_base_url,
    )
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        num_ctx=settings.num_ctx,  # CRITICAL - default 2048 truncates silently
        temperature=settings.temperature,
        keep_alive=settings.keep_alive,
        reasoning=settings.llm_reasoning,
        num_predict=settings.llm_num_predict,
        client_kwargs={"timeout": settings.llm_timeout_s},
    )


def build_groq() -> BaseChatModel:
    if not settings.groq_api_key.get_secret_value():
        raise BackendError(
            "BA_GROQ_API_KEY is not set. Put it in .env - see .env.example - "
            "or run with --backend ollama."
        )
    from langchain_groq import ChatGroq

    log.info("connecting to groq model=%s", settings.groq_model)
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key.get_secret_value(),
        temperature=settings.temperature,
        max_tokens=settings.llm_num_predict,
        timeout=settings.groq_timeout_s,
        # Handled here instead: langchain's own retry does not count tokens and
        # cannot fall back to another backend.
        max_retries=0,
    )


def client(backend: str) -> BaseChatModel:
    """The configured client for one backend, built once and kept."""
    if backend not in BACKENDS:
        raise BackendError(f"unknown backend {backend!r}; expected one of {BACKENDS}")
    if backend not in _clients:
        _clients[backend] = build_ollama() if backend == OLLAMA else build_groq()
    return _clients[backend]


def reset_clients() -> None:
    _clients.clear()
    reset_limiter()


# --------------------------------------------------------------------------
# invocation
# --------------------------------------------------------------------------


def is_permanent(error: Exception) -> bool:
    """Errors that will fail identically on every retry.

    A wrong model name, a bad key, a revoked key. Retrying these three times a
    line - and spending limiter budget to do it - turns a one-line
    configuration mistake into a twenty-minute run that fails anyway. Seen
    exactly once, with a retired model id.
    """
    text = str(error).lower()
    return (
        "model_not_found" in text
        or "does not exist or you do not have access" in text
        or "invalid_api_key" in text
        or "401" in text
        or "403" in text
    )


class Unreachable(BackendError):
    """The hosted backend cannot be reached. Fall back and carry on.

    This is the demo case: bad venue wifi. Groq gives you nothing, Ollama is on
    the laptop, and the audit should finish rather than stop half way.
    """


def is_unreachable(error: Exception) -> bool:
    """A network problem or a server-side fault, as opposed to our mistake."""
    text = str(error).lower()
    if isinstance(error, ConnectionError | TimeoutError):
        return True
    return any(
        needle in text
        for needle in (
            "connection",
            "timeout",
            "timed out",
            "temporary failure in name resolution",
            "name or service not known",
            "network is unreachable",
            "502",
            "503",
            "504",
            "internal server error",
            "apiconnectionerror",
        )
    )


def is_rate_limited(error: Exception) -> bool:
    text = str(error).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


def is_daily_quota(error: Exception) -> bool:
    """A day's allowance gone, as opposed to a minute's.

    Groq words these differently, and the difference matters: a minute is worth
    waiting out, a day is not.
    """
    text = str(error).lower()
    return "per day" in text or "requests per day" in text or "daily" in text


def retry_after(error: Exception) -> float | None:
    """Groq usually names the wait in the message; use it when it does."""
    import re

    match = re.search(r"try again in ([\d.]+)\s*s", str(error), re.I)
    return float(match.group(1)) if match else None


def guard_pii(messages: list[Any]) -> None:
    """Nothing with an identifier in it leaves this machine.

    Masking already runs at intake, so this should never fire. It exists
    because "should never" and "cannot" are different guarantees, and only one
    of them is worth having when the text is about to cross a network.
    """
    for message in messages:
        content = str(getattr(message, "content", message))
        if contains_pii(content):
            raise PIIWouldLeave(
                "refusing to send text to a hosted backend: it still contains "
                "something that looks like a phone number, an Aadhaar number or "
                "an email address"
            )


def invoke(backend: str, messages: list[Any], *, structured: Any = None) -> Any:
    """One call, with this backend's rules applied.

    Ollama is called directly - it has no quota to respect. Groq is metered,
    retried with backoff on 429, and gives up to the caller when the day is
    gone rather than failing the audit.
    """
    model = client(backend)
    runnable = model.with_structured_output(structured) if structured is not None else model

    if backend == OLLAMA:
        return runnable.invoke(messages)

    guard_pii(messages)
    estimate = estimate_tokens(messages)
    last: Exception | None = None

    for attempt in range(1, settings.groq_max_retries + 1):
        limiter().acquire(estimate)
        try:
            return runnable.invoke(messages)
        except Exception as exc:
            last = exc
            if is_permanent(exc):
                # BackendError so the caller stops rather than retrying.
                raise BackendError(str(exc)) from exc
            if is_unreachable(exc):
                # Not our mistake and not a quota - the network. Hand it up so
                # the local model can finish the job.
                raise Unreachable(str(exc)) from exc
            if not is_rate_limited(exc):
                raise
            if is_daily_quota(exc):
                limiter().note_quota_exhausted()
                raise QuotaExhausted(str(exc)) from exc
            wait = retry_after(exc) or settings.groq_backoff_base_s * (2 ** (attempt - 1))
            log.warning(
                "groq rate limited (attempt %d/%d), backing off %.1fs",
                attempt,
                settings.groq_max_retries,
                wait,
            )
            time.sleep(wait)

    raise BackendError(f"groq refused {settings.groq_max_retries} times: {last}")
