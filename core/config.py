"""Single source of truth for paths, model names and tuning knobs.

Everything is overridable from the environment with a `BA_` prefix, or from a
`.env` file at the repo root. See `.env.example` for the full list.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_prefix="BA_",
        extra="ignore",
    )

    # --- Ollama ---------------------------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    # CRITICAL: Ollama defaults to 2048 and truncates retrieved clauses with
    # no warning. Anything smaller than 8192 silently corrupts the verdicts.
    num_ctx: int = 8192
    temperature: float = 0.0
    keep_alive: str = "30m"
    llm_timeout_s: int = 180

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
