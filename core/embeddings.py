"""Sentence-transformer embeddings behind the LangChain interface.

Wrapped by hand rather than pulled from `langchain-huggingface` to keep the
dependency surface small, and because BGE needs an asymmetric prefix: queries
are embedded with an instruction, documents without it. Skipping that prefix
costs a few points of retrieval accuracy for no obvious reason, which is
exactly the kind of silent bug this project cannot afford.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import TYPE_CHECKING

from langchain_core.embeddings import Embeddings

from core.config import settings
from core.logging_conf import get_logger

if TYPE_CHECKING:  # sentence_transformers pulls torch; see _load
    from sentence_transformers import SentenceTransformer

log = get_logger(__name__)

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# Guards the load below. `lru_cache` is not atomic: two threads that miss
# together both run the body, and two SentenceTransformers loading the same
# weights at once is not merely wasteful - it took the eval down on the first
# run after bill lines started being judged in parallel, with "loading
# embedding model" logged twice and a leaked semaphore on the way out.
#
# The services warm this at startup so it is built before any request; the eval
# and the CLI have no warm-up, which is where it bit.
_load_lock = threading.Lock()

# Held across every forward pass, embedding or rerank.
#
# On a Mac the models land on the MPS device, and two threads sharing one
# Metal command buffer is not slow, it is fatal:
#
#     failed assertion _status < MTLCommandBufferStatusCommitted
#     at -[IOGPUMetalCommandBuffer setCurrentCommandEncoder:]
#
# followed by SIGABRT. The eval died on bill one every run once lines were
# judged in parallel. The containers ship CPU-only torch and never see it,
# which is exactly why it has to be handled here rather than left to whoever
# next runs the eval on a laptop.
#
# Serialising costs almost nothing, and that is measured rather than hoped:
# two workers beat one by 1.27x precisely because a single search already
# saturates every core, so the forward passes were never really overlapping.
INFERENCE_LOCK = threading.RLock()


@lru_cache(maxsize=2)
def _cached_load(model_name: str) -> SentenceTransformer:
    """Imported here, not at the top, because it drags in torch.

    Only retrieval and ingestion ever embed anything. Importing this module is
    not the same as needing a 2 GB tensor library, and the gateway and the
    audit service reach `core.ingest` - which reaches this - just to read
    clauses.json.
    """
    from core.cpu import apply_torch_threads

    # Before the weights load, so the thread pool is the right size the first
    # time it is used rather than after a forward pass has already been queued.
    apply_torch_threads()

    from sentence_transformers import SentenceTransformer

    device = settings.torch_device or None
    log.info("loading embedding model %s on %s", model_name, device or "the default device")
    return SentenceTransformer(model_name, device=device)


def _load(model_name: str) -> SentenceTransformer:
    with _load_lock:
        return _cached_load(model_name)


class BGEEmbeddings(Embeddings):
    """bge-base-en-v1.5, normalised so cosine distance behaves."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model

    @property
    def model(self) -> SentenceTransformer:
        return _load(self.model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with INFERENCE_LOCK:
            vectors = self.model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=len(texts) > 64,
            )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        with INFERENCE_LOCK:
            vector = self.model.encode(
                QUERY_PREFIX + text,
                normalize_embeddings=True,
            )
        return vector.tolist()


@lru_cache(maxsize=1)
def get_embeddings() -> BGEEmbeddings:
    return BGEEmbeddings()
