"""Single source of truth for paths, model names and tuning knobs.

Everything is overridable from the environment with a `BA_` prefix, or from a
`.env` file at the repo root. See `.env.example` for the full list.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_prefix="BA_",
        extra="ignore",
    )

    # --- Which backend, and where the default comes from ----------------
    #
    # Two backends, used for different things:
    #
    #   ollama  local Qwen3 8B. Slow per call (~11s a line), no rate limit,
    #           works offline. The only sane choice for a 44-bill eval, which
    #           is ~400 calls.
    #   groq    hosted Llama 3.3 70B. About a second a call, but the free tier
    #           is 30 requests and 6,000 tokens a minute, 1,000 requests a day.
    #           The right choice for one person waiting on one bill.
    #
    # The default differs by context, and every default lives here rather than
    # being decided at each call site. `BA_LLM_BACKEND` overrides all of them,
    # which is how docker and k8s pick a backend with no code change.
    llm_backend: str = ""  # blank means "use the context default below"
    llm_backend_api: str = "groq"  # a person is waiting
    llm_backend_eval: str = "ollama"  # hundreds of calls, no quota to burn
    llm_backend_cli: str = "ollama"  # also the default for tests

    # --- Groq -----------------------------------------------------------
    # The key is read from .env and nothing else. There is no default and it is
    # never committed; see .env.example.
    # SecretStr, so the key cannot be printed by accident. repr() and str() of
    # the settings object show "**********", and it takes an explicit
    # .get_secret_value() to read it - which happens in exactly one place.
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-120b"
    # Free-tier limits, read from Groq's own x-ratelimit headers rather than
    # guessed. The token cap binds long before the request cap: 8,000 tokens a
    # minute is three to six judge calls, well under the 30 requests the same
    # minute allows. Check yours with the curl in the README - they differ by
    # model and by account.
    groq_tokens_per_minute: int = 8000
    groq_requests_per_minute: int = 30
    groq_requests_per_day: int = 1000
    groq_max_retries: int = 4
    groq_backoff_base_s: float = 2.0
    groq_timeout_s: int = 60

    # --- Ollama ---------------------------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    # CRITICAL: Ollama defaults to 2048 and truncates retrieved clauses with
    # no warning. Anything smaller than 8192 silently corrupts the verdicts.
    num_ctx: int = 8192
    temperature: float = 0.0
    keep_alive: str = "30m"
    llm_timeout_s: int = 180
    # qwen3 "thinks" before answering by default, which costs roughly five times
    # the latency. Classification and structured judging at temperature 0 do not
    # benefit from it. Flip this on and re-run the eval if the numbers say
    # otherwise - that is exactly the kind of question Phase 5 exists to settle.
    llm_reasoning: bool = False
    # Hard cap on generated tokens. Without it a looping model streams forever:
    # the HTTP read timeout never fires because every token resets it, so the
    # call hangs indefinitely with the process idle at 1% CPU. This is the only
    # thing that actually bounds a runaway generation.
    llm_num_predict: int = 2048

    # --- LLM disk cache -------------------------------------------------
    llm_cache_enabled: bool = True

    # --- Retrieval ------------------------------------------------------
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    chroma_top_k: int = 20
    bm25_top_k: int = 20
    dense_weight: float = 0.6
    sparse_weight: float = 0.4
    rerank_top_n: int = 3
    # Below this rerank score nothing retrieved is relevant enough to judge on;
    # guardrail 5 skips the LLM entirely and flags for human review.
    rerank_score_threshold: float = 0.30

    # --- Agent loop -----------------------------------------------------
    max_attempts: int = 3
    max_tool_calls: int = 8
    structured_output_retries: int = 2

    # --- Services (Phase 10) ---
    # Empty means "do it in this process", which is how the monolith in api/
    # and the eval both run. docker-compose fills these in with service names.
    retrieval_url: str = ""
    audit_url: str = "http://audit-service:8000"
    ingestion_url: str = "http://ingestion-service:8000"
    service_timeout_s: int = 300

    # --- API ---
    # The React dev server. Listed here rather than in api/ so every setting
    # stays in one file and can be overridden with BA_CORS_ORIGINS.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    max_upload_mb: int = 25
    max_jobs_kept: int = 100

    # --- Logging --------------------------------------------------------
    log_level: str = "INFO"

    # --- Derived paths --------------------------------------------------
    @property
    def root_dir(self) -> Path:
        return ROOT_DIR

    @property
    def data_dir(self) -> Path:
        return ROOT_DIR / "data"

    @property
    def policies_dir(self) -> Path:
        return self.data_dir / "policies"

    @property
    def clauses_path(self) -> Path:
        """Checkpoint written by ingestion step S7."""
        return self.data_dir / "clauses.json"

    @property
    def non_payable_path(self) -> Path:
        """IRDAI List I names, written by ingestion step S11."""
        return self.data_dir / "non_payable.json"

    def backend_for(self, context: str) -> str:
        """The backend for a context, honouring an explicit override.

        `context` is one of "api", "eval" or "cli". An explicit BA_LLM_BACKEND
        wins everywhere - that is what lets docker and k8s choose without a
        code change - and otherwise the context decides.
        """
        if self.llm_backend:
            return self.llm_backend
        return {
            "api": self.llm_backend_api,
            "eval": self.llm_backend_eval,
        }.get(context, self.llm_backend_cli)

    @property
    def llm_cache_dir(self) -> Path:
        return self.data_dir / "llm_cache"

    @property
    def db_dir(self) -> Path:
        """ChromaDB PersistentClient directory."""
        return self.data_dir / "db"

    @property
    def traces_dir(self) -> Path:
        return self.data_dir / "traces"

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.policies_dir,
            self.llm_cache_dir,
            self.db_dir,
            self.traces_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
