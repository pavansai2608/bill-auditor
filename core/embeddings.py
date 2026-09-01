"""Sentence-transformer embeddings behind the LangChain interface.

Wrapped by hand rather than pulled from `langchain-huggingface` to keep the
dependency surface small, and because BGE needs an asymmetric prefix: queries
are embedded with an instruction, documents without it. Skipping that prefix
costs a few points of retrieval accuracy for no obvious reason, which is
exactly the kind of silent bug this project cannot afford.
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from core.config import settings
from core.logging_conf import get_logger

log = get_logger(__name__)

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=2)
def _load(model_name: str) -> SentenceTransformer:
    log.info("loading embedding model %s", model_name)
    return SentenceTransformer(model_name)


class BGEEmbeddings(Embeddings):
    """bge-base-en-v1.5, normalised so cosine distance behaves."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model

    @property
    def model(self) -> SentenceTransformer:
        return _load(self.model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=len(texts) > 64,
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self.model.encode(
            QUERY_PREFIX + text,
            normalize_embeddings=True,
        )
        return vector.tolist()


@lru_cache(maxsize=1)
def get_embeddings() -> BGEEmbeddings:
    return BGEEmbeddings()
