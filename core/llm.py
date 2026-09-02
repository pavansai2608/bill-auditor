"""LLM access for both backends, with a disk cache in front of them.

`core.backends` owns the difference between Ollama and Groq - the limits, the
backoff, the fallback. This module owns what is the same for both: building
messages, the cache, structured output, and the retry on invalid output.

Three things matter here.

`num_ctx=8192`: Ollama's default context is 2048 tokens. Retrieved clauses get
silently truncated at that size and the model answers confidently from half a
clause. There is no error and no warning, so it must be set explicitly.

The cache: evaluation re-runs the same 40 bills dozens of times. Every call is
keyed by a sha256 of the model settings plus the exact messages, and the
response is stored as JSON under `data/llm_cache/`. A repeated prompt is
answered from disk and never reaches the model.

The cache key includes the backend and the model. Without that, a Qwen answer
cached this morning would be served this afternoon as if Llama had said it -
silently, and with no way to tell from the report.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from core import backends
from core.backends import GROQ, OLLAMA, QuotaExhausted, Unreachable
from core.config import settings
from core.logging_conf import get_logger

log = get_logger(__name__)

# Verification hook: after two identical calls this must read hits=1, misses=1.
CACHE_STATS: dict[str, int] = {"hits": 0, "misses": 0, "writes": 0}


class LLMError(RuntimeError):
    """Raised when the model cannot produce a usable answer."""


# --------------------------------------------------------------------------
# client
# --------------------------------------------------------------------------

# The backend in force for this process. Set once, at the edge that knows the
# context: the API sets "api", the eval sets "eval", everything else gets the
# CLI default. Nothing decides this per call.
_backend: str | None = None

# Set when a Groq call has fallen back to Ollama, so the report can say so.
# A user should never be shown a half-finished audit because a free tier ran
# out at line seven, and should never be shown a complete one that quietly
# changed model half way either.
FELL_BACK: dict[str, Any] = {"happened": False, "reason": ""}


def use_backend(name: str) -> str:
    """Fix the backend for this process. Returns what was chosen."""
    global _backend
    if name not in backends.BACKENDS:
        raise backends.BackendError(f"unknown backend {name!r}")
    _backend = name
    log.info("llm backend is %s", name)
    return name


def active_backend() -> str:
    """The backend in force, defaulting to the CLI context."""
    return _backend or settings.backend_for("cli")


def get_llm():
    """The configured client for the active backend."""
    return backends.client(active_backend())


def reset_client() -> None:
    """Drop the cached clients so changed settings take effect. Tests use this."""
    global _backend
    _backend = None
    FELL_BACK["happened"] = False
    FELL_BACK["reason"] = ""
    backends.reset_clients()


def _invoke(messages: list[BaseMessage], structured: Any = None) -> Any:
    """One call on the active backend, falling back when the day runs out.

    The fallback is the whole reason this is not just `client().invoke(...)`.
    Groq's free tier ends abruptly, and it can end mid-audit; carrying on with
    Ollama is slower but finishes, which is what the person waiting wants.
    """
    backend = active_backend()
    try:
        return backends.invoke(backend, messages, structured=structured)
    except (QuotaExhausted, Unreachable) as problem:
        if backend != GROQ:
            raise
        FELL_BACK["happened"] = True
        FELL_BACK["reason"] = str(problem)
        why = "quota exhausted" if isinstance(problem, QuotaExhausted) else "unreachable"
        log.warning("groq %s, falling back to ollama: %s", why, problem)
        use_backend(OLLAMA)
        return backends.invoke(OLLAMA, messages, structured=structured)


# --------------------------------------------------------------------------
# disk cache
# --------------------------------------------------------------------------


def _messages_payload(messages: list[BaseMessage]) -> list[dict[str, str]]:
    return [{"role": m.type, "content": str(m.content)} for m in messages]


def cache_key(messages: list[BaseMessage], schema_name: str | None) -> str:
    """sha256 over everything that could change the answer."""
    backend = active_backend()
    payload = {
        # Both, and always. A key without the backend would serve a Qwen answer
        # as a Llama one after a switch, with nothing in the report to show it.
        "backend": backend,
        "model": settings.groq_model if backend == GROQ else settings.ollama_model,
        "num_ctx": settings.num_ctx,
        "temperature": settings.temperature,
        "reasoning": settings.llm_reasoning,
        "num_predict": settings.llm_num_predict,
        "schema": schema_name,
        "messages": _messages_payload(messages),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return settings.llm_cache_dir / f"{key}.json"


def cache_get(key: str) -> Any | None:
    if not settings.llm_cache_enabled:
        return None
    path = _cache_path(key)
    if not path.exists():
        CACHE_STATS["misses"] += 1
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            entry = json.load(fh)
    except json.JSONDecodeError, OSError:
        # A half-written cache file must never take the system down.
        log.warning("discarding unreadable cache entry %s", path.name)
        path.unlink(missing_ok=True)
        CACHE_STATS["misses"] += 1
        return None
    CACHE_STATS["hits"] += 1
    log.debug("cache hit %s", key[:12])
    return entry["response"]


def cache_put(key: str, response: Any, meta: dict[str, Any]) -> None:
    if not settings.llm_cache_enabled:
        return
    settings.llm_cache_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "key": key,
        "backend": active_backend(),
        "model": settings.groq_model if active_backend() == GROQ else settings.ollama_model,
        "num_ctx": settings.num_ctx,
        "created_at": time.time(),
        **meta,
        "response": response,
    }
    tmp = _cache_path(key).with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(entry, fh, ensure_ascii=False, indent=2, default=str)
    tmp.replace(_cache_path(key))
    CACHE_STATS["writes"] += 1


def clear_cache() -> int:
    """Delete every cached response. Returns how many were removed."""
    removed = 0
    for path in settings.llm_cache_dir.glob("*.json"):
        path.unlink()
        removed += 1
    return removed


# --------------------------------------------------------------------------
# calls
# --------------------------------------------------------------------------


def _build_messages(prompt: str, system: str | None) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    return messages


def complete(prompt: str, *, system: str | None = None) -> str:
    """Free-text completion, cached."""
    messages = _build_messages(prompt, system)
    key = cache_key(messages, schema_name=None)

    cached = cache_get(key)
    if cached is not None:
        return str(cached)

    started = time.perf_counter()
    response = _invoke(messages)
    text = str(response.content)
    log.debug("llm call took %.2fs", time.perf_counter() - started)

    cache_put(key, text, {"kind": "text", "messages": _messages_payload(messages)})
    return text


def complete_structured[TModel: BaseModel](
    prompt: str,
    schema: type[TModel],
    *,
    system: str | None = None,
    retries: int | None = None,
) -> TModel:
    """Completion validated against a Pydantic schema, cached.

    Retries on invalid output (R4). Only valid results are ever cached, so a
    rejected response costs nothing on the next run.
    """
    messages = _build_messages(prompt, system)
    key = cache_key(messages, schema_name=schema.__name__)

    cached = cache_get(key)
    if cached is not None:
        try:
            return schema.model_validate(cached)
        except ValidationError:
            # The schema changed since this was cached. Drop it and re-ask.
            log.warning("cached entry no longer matches %s, refetching", schema.__name__)
            _cache_path(key).unlink(missing_ok=True)

    attempts = (retries if retries is not None else settings.structured_output_retries) + 1
    # Same structured-output path on both backends, so JudgeOutput parses
    # identically whichever answered.
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            result = _invoke(messages, schema)
        except backends.BackendError:
            # A missing key, or text that still has an identifier in it. Neither
            # gets better on the second try, and retrying buries the reason.
            raise
        except Exception as exc:  # ollama down, malformed JSON, schema mismatch
            last_error = exc
            log.warning(
                "structured call failed (%d/%d) for %s: %s",
                attempt,
                attempts,
                schema.__name__,
                exc,
            )
            continue

        if not isinstance(result, schema):
            try:
                result = schema.model_validate(result)
            except ValidationError as exc:
                last_error = exc
                log.warning("output did not validate (%d/%d)", attempt, attempts)
                continue

        cache_put(
            key,
            result.model_dump(),
            {
                "kind": "structured",
                "schema": schema.__name__,
                "messages": _messages_payload(messages),
            },
        )
        return result

    raise LLMError(
        f"{schema.__name__} not produced after {attempts} attempts: {last_error}"
    ) from last_error
