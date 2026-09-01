"""Hybrid retrieval: dense + lexical, sub-chunked, then reranked.

Four stages, each earning its place:

1. **Dense** (Chroma, cosine over bge-base) finds clauses that *mean* the same
   thing as the query - "room charges cap" matching "Room Rent limit".
2. **Lexical** (BM25) finds clauses that use the exact words. Policy documents
   are full of terms that must match literally: "Aggregate Deductible",
   "Excl03", "Vasofix Safety". Embeddings blur precisely those.
3. **Sub-chunking** splits any long clause into sentence windows *before*
   reranking. Star Health states its room rent rule inside a 3,000-character
   "In-patient Treatment" clause; scored whole, the one relevant sentence is
   drowned by paragraphs about ambulances and AYUSH. Each window carries its
   parent's clause_id, so a citation still resolves to the real clause.
4. **Reranking** (bge-reranker-base cross-encoder) reads query and clause
   together rather than comparing two independent vectors, and is far more
   accurate than either retriever - but too slow to run over 356 clauses, which
   is why it only ever sees the ~40 candidates the first two stages surface.

Everything is filtered to a single policy: auditing a Star Health bill against
an HDFC clause would be a fabricated citation of the worst kind.
"""

import re
from functools import lru_cache
from typing import Any

from langchain_classic.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain_classic.retrievers.document_compressors import DocumentCompressorPipeline
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentTransformer, Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from pydantic import Field

from core.config import settings
from core.embeddings import get_embeddings
from core.ingest import COLLECTION, build_bm25, load_clauses
from core.logging_conf import get_logger
from core.models import Clause

log = get_logger(__name__)

# Clauses longer than this are scored as sentence windows instead of whole.
SUB_CHUNK_THRESHOLD = 1500
SUB_CHUNK_TARGET = 600
# Cross-referenced clauses ride along with the clause that names them.
MAX_REF_PULLS = 4
MAX_REF_CHARS = 900
# Sentence boundary. Deliberately hand-rolled: a LangChain text splitter would
# cut mid-clause on a character count and is banned on these documents.
SENTENCE_RE = re.compile(r"(?<=[.;:])\s+")


# --------------------------------------------------------------------------
# sub-chunking
# --------------------------------------------------------------------------


def sentence_windows(text: str, target: int = SUB_CHUNK_TARGET) -> list[str]:
    """Pack sentences into overlapping windows of roughly `target` characters.

    One sentence of overlap, so a rule split across a boundary ("...the limit
    is 1% of Sum Insured. Where this is exceeded, all other charges...") still
    appears intact in one window.
    """
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return []

    windows: list[str] = []
    current: list[str] = []
    size = 0
    for sentence in sentences:
        if current and size + len(sentence) > target:
            windows.append(" ".join(current))
            current = current[-1:]  # carry the last sentence forward
            size = len(current[0])
        current.append(sentence)
        size += len(sentence)
    if current:
        windows.append(" ".join(current))
    return windows


class ClauseSubChunker(BaseDocumentTransformer):
    """Split long clauses into sentence windows so each competes on its own.

    The parent clause_id is copied onto every window, so whichever window wins
    the rerank still cites the clause a human can look up.
    """

    def __init__(self, threshold: int = SUB_CHUNK_THRESHOLD) -> None:
        self.threshold = threshold

    def transform_documents(self, documents: list[Document], **kwargs: Any) -> list[Document]:
        out: list[Document] = []
        for document in documents:
            if len(document.page_content) <= self.threshold:
                out.append(document)
                continue

            title = document.metadata.get("title", "")
            windows = sentence_windows(document.page_content)
            for index, window in enumerate(windows):
                metadata = dict(document.metadata)
                metadata["sub_chunk"] = index
                metadata["sub_chunk_of"] = document.metadata.get("clause_id")
                out.append(
                    # The title rides along so the cross-encoder keeps the
                    # context a bare middle-of-clause window would lack.
                    Document(page_content=f"{title}\n{window}".strip(), metadata=metadata)
                )
        return out

    async def atransform_documents(
        self, documents: list[Document], **kwargs: Any
    ) -> list[Document]:
        return self.transform_documents(documents, **kwargs)


# --------------------------------------------------------------------------
# reranking
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_cross_encoder() -> HuggingFaceCrossEncoder:
    log.info("loading reranker %s", settings.reranker_model)
    return HuggingFaceCrossEncoder(model_name=settings.reranker_model)


class ClauseReranker(BaseDocumentCompressor):
    """Cross-encoder rerank that collapses sub-chunks back to one per clause.

    Without the collapse, all three top slots can be three windows of the same
    clause and the judge sees one clause instead of three candidates.
    """

    top_n: int = Field(default_factory=lambda: settings.rerank_top_n)

    model_config = {"arbitrary_types_allowed": True}

    def compress_documents(
        self,
        documents: list[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> list[Document]:
        if not documents:
            return []

        scores = get_cross_encoder().score([(query, d.page_content) for d in documents])

        best: dict[str, tuple[float, Document]] = {}
        for document, score in zip(documents, scores, strict=True):
            key = f"{document.metadata.get('policy')}:{document.metadata.get('clause_id')}"
            if key not in best or score > best[key][0]:
                best[key] = (float(score), document)

        ranked = sorted(best.values(), key=lambda pair: pair[0], reverse=True)

        out: list[Document] = []
        for score, document in ranked[: self.top_n]:
            enriched = Document(
                page_content=document.page_content, metadata=dict(document.metadata)
            )
            enriched.metadata["relevance_score"] = score
            out.append(enriched)
        return out


# --------------------------------------------------------------------------
# retrievers
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_vector_store():
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(settings.db_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )


@lru_cache(maxsize=4)
def _clauses_for(policy: str) -> tuple[Clause, ...]:
    return tuple(c for c in load_clauses() if c.policy == policy)


@lru_cache(maxsize=4)
def get_hybrid_retriever(policy: str) -> EnsembleRetriever:
    """Dense + BM25 over one policy, fused by reciprocal rank.

    Weighted 0.6 dense / 0.4 lexical: semantic match carries most queries, but
    the exact-term channel is what rescues codes and proper nouns.
    """
    clauses = _clauses_for(policy)
    if not clauses:
        raise ValueError(f"no clauses indexed for policy {policy!r}")

    dense = get_vector_store().as_retriever(
        search_kwargs={"k": settings.chroma_top_k, "filter": {"policy": policy}}
    )
    sparse = build_bm25(list(clauses))
    sparse.k = settings.bm25_top_k

    return EnsembleRetriever(
        retrievers=[dense, sparse],
        weights=[settings.dense_weight, settings.sparse_weight],
    )


@lru_cache(maxsize=4)
def get_retriever(policy: str) -> ContextualCompressionRetriever:
    """The full stack: hybrid retrieve, sub-chunk, rerank to the top few."""
    pipeline = DocumentCompressorPipeline(transformers=[ClauseSubChunker(), ClauseReranker()])
    return ContextualCompressionRetriever(
        base_compressor=pipeline,
        base_retriever=get_hybrid_retriever(policy),
    )


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------


class RetrievedClause:
    """A clause the retriever surfaced, with the score that got it there."""

    def __init__(
        self,
        clause: Clause,
        score: float,
        matched_text: str,
        via_ref_of: str | None = None,
    ) -> None:
        self.clause = clause
        self.score = score
        # The window that actually scored, which is what the judge should read
        # when the parent clause is long.
        self.matched_text = matched_text
        # Set when this clause was pulled in because another clause named it,
        # rather than because it matched the query.
        self.via_ref_of = via_ref_of

    def __repr__(self) -> str:
        via = f" via {self.via_ref_of}" if self.via_ref_of else ""
        return (
            f"<RetrievedClause {self.clause.policy}:{self.clause.clause_id} {self.score:.3f}{via}>"
        )


def with_references(
    results: list[RetrievedClause], policy: str, *, limit: int = MAX_REF_PULLS
) -> list[RetrievedClause]:
    """Pull in clauses that the retrieved ones name.

    Star Health's co-payment clause applies only to "Coverages II.1, II.2, ...
    II.13" - retrieving it without that list invites applying a 20% cut to a
    line it does not cover. The judge cannot ask for a clause it was not given,
    so the clauses a clause names come along with it.

    This is the cheap half of the problem. A reference stated in prose ("the
    waiting period specified for pre-existing diseases") is not caught here,
    and needs the agent to say what it is missing - Phase 6.
    """
    index = {c.clause_id: c for c in _clauses_for(policy)}
    have = {r.clause.clause_id for r in results}
    extra: list[RetrievedClause] = []

    for result in results:
        for ref in result.clause.refs:
            if ref in have or len(extra) >= limit:
                continue
            clause = index.get(ref)
            if clause is None:
                continue
            have.add(ref)
            extra.append(
                RetrievedClause(
                    clause=clause,
                    score=0.0,
                    matched_text=clause.text[:MAX_REF_CHARS],
                    via_ref_of=result.clause.clause_id,
                )
            )
    return results + extra


def search(
    query: str, policy: str, *, top_n: int | None = None, follow_refs: bool = True
) -> list[RetrievedClause]:
    """Find the clauses most likely to decide this query, best first."""
    retriever = get_retriever(policy)
    documents = retriever.invoke(query)

    index = {c.clause_id: c for c in _clauses_for(policy)}
    results: list[RetrievedClause] = []
    for document in documents:
        clause = index.get(document.metadata.get("clause_id", ""))
        if clause is None:
            # A vector left over from an older index. Skip it rather than let a
            # citation point at a clause that is no longer in clauses.json.
            log.warning("retrieved unknown clause_id %s", document.metadata.get("clause_id"))
            continue
        results.append(
            RetrievedClause(
                clause=clause,
                score=float(document.metadata.get("relevance_score", 0.0)),
                matched_text=document.page_content,
            )
        )

    limit = top_n if top_n is not None else settings.rerank_top_n
    results = results[:limit]
    return with_references(results, policy) if follow_refs else results


def main() -> None:
    import argparse

    from core.logging_conf import setup_logging

    parser = argparse.ArgumentParser(description="Search policy clauses")
    parser.add_argument("query")
    parser.add_argument("--policy", default="hdfc_ergo")
    parser.add_argument("--top-n", type=int, default=None)
    args = parser.parse_args()

    setup_logging()
    for result in search(args.query, args.policy, top_n=args.top_n):
        clause = result.clause
        print(
            f"\n{result.score:7.3f}  {clause.clause_id:<14} p{clause.page:<3} [{clause.rule_type}]"
        )
        print(f"         {clause.title[:70]}")
        print(f"         {result.matched_text[:200].replace(chr(10), ' ')}...")


if __name__ == "__main__":
    main()
