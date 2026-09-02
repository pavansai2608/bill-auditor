"""Offline setup: policy PDFs in, searchable clause index out (S1-S11).

Runs once and is then cached at two levels. `data/clauses.json` is the
checkpoint (S7): parsing and labelling 300+ clauses costs several minutes of
model time, and nothing downstream should ever pay that twice. The Chroma
store under `data/db/` is the second. Both are rebuilt only with `--force`.
"""

import argparse
import json
import re
from pathlib import Path

from pydantic import BaseModel

from core.config import settings
from core.llm import complete_structured
from core.logging_conf import get_logger, setup_logging
from core.models import Clause, RuleType

log = get_logger(__name__)


# Imported on use, not on import. This module is the doorway to clauses.json,
# so the gateway and the audit service both import it - and neither has any
# business pulling in pdfplumber or a tensor library to read a JSON file.
def _split_pdf():
    from core.splitter import split_pdf

    return split_pdf


def _embeddings():
    from core.embeddings import get_embeddings

    return get_embeddings()


COLLECTION = "policy_clauses"

POLICY_FILES = {
    "star_health": "star_health.pdf",
    "hdfc_ergo": "hdfc_ergo.pdf",
    "niva_bupa": "niva_bupa.pdf",
}
NON_PAYABLE_FILE = "non_payable_items.pdf"


# --------------------------------------------------------------------------
# S6 - rule_type labelling
# --------------------------------------------------------------------------


class ClauseLabel(BaseModel):
    """The rule_type for a single clause.

    One clause per call, deliberately. Two batched designs were tried first and
    both failed silently. Asking the model to echo the clause_id back cost every
    star_health label, because it copied the brackets from the prompt. Switching
    to positional indices was worse: the model lost count part-way through a
    batch, so labels landed on the wrong clauses and "Policy Schedule" came back
    tagged room_rent. A single-clause call has no identifier to mangle and no
    ordering to lose. It costs more calls, but every one is cached on disk, so
    the price is paid once and adding a clause later re-labels only that clause.
    """

    rule_type: RuleType


LABEL_SYSTEM = """You classify clauses from Indian health insurance policies.

Assign exactly one rule_type to the clause:
- room_rent      : caps or conditions on room/bed/ICU charges per day, room category,
                   or proportionate deduction when the room limit is exceeded
- non_payable    : items the policy never pays for (consumables, excluded expenses)
- sub_limit      : a monetary or percentage cap on a specific treatment or benefit
- copay          : a share of the claim the insured must bear
- waiting_period : time that must pass before a cover starts
- other          : definitions, procedures, administration, anything else

Most clauses are "other". Only use a specific type when the clause actually
states that rule."""


def _label_prompt(clause: Clause) -> str:
    return f"Clause title: {clause.title}\n\nClause text:\n{clause.text[:1200]}"


def label_rule_types(clauses: list[Clause]) -> list[Clause]:
    """S6 - tag every clause with the rule it expresses.

    A failed call leaves the clause as "other" rather than aborting: one bad
    label costs a little routing precision, a crashed ingestion costs the run.
    """
    labelled = 0
    for position, clause in enumerate(clauses, start=1):
        if position % 25 == 0 or position == 1:
            log.info("labelling clause %d/%d", position, len(clauses))
        try:
            result = complete_structured(_label_prompt(clause), ClauseLabel, system=LABEL_SYSTEM)
        except Exception as exc:  # a bad clause must not kill the whole ingestion
            log.warning("labelling failed for %s: %s", clause.clause_id, exc)
            continue
        clause.rule_type = result.rule_type
        labelled += 1

    coverage = labelled / len(clauses) if clauses else 0
    log.info("labelled %d/%d clauses (%.0f%%)", labelled, len(clauses), coverage * 100)
    if coverage < 0.9:
        # Loud, because the failure mode is silent: everything defaults to
        # "other", retrieval still works, and the agent just routes badly.
        log.error(
            "labelling coverage is only %.0f%% - rule_type routing will be unreliable",
            coverage * 100,
        )
    return clauses


# --------------------------------------------------------------------------
# S1-S7 - clauses.json
# --------------------------------------------------------------------------


def build_clauses() -> list[Clause]:
    """S1-S6: read every policy PDF, split it, label it."""
    clauses: list[Clause] = []
    for policy, filename in POLICY_FILES.items():
        path = settings.policies_dir / filename
        if not path.exists():
            log.warning("missing %s, skipping %s", path, policy)
            continue
        clauses.extend(_split_pdf()(path, policy))

    if not clauses:
        raise FileNotFoundError(
            f"no policy PDFs found in {settings.policies_dir}. "
            "Add star_health.pdf, hdfc_ergo.pdf and niva_bupa.pdf."
        )
    return label_rule_types(clauses)


def save_clauses(clauses: list[Clause]) -> Path:
    """S7 - the checkpoint. Never skip it."""
    settings.clauses_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [c.model_dump() for c in clauses]
    settings.clauses_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("wrote %d clauses to %s", len(clauses), settings.clauses_path)
    return settings.clauses_path


def load_clauses() -> list[Clause]:
    """Read the checkpoint. Every later phase starts here."""
    if not settings.clauses_path.exists():
        raise FileNotFoundError(
            f"{settings.clauses_path} not found - run 'uv run python -m core.ingest' first"
        )
    raw = json.loads(settings.clauses_path.read_text(encoding="utf-8"))
    return [Clause.model_validate(item) for item in raw]


def clause_index() -> dict[str, Clause]:
    """Lookup used by guardrail 2 to reject fabricated citations."""
    return {f"{c.policy}:{c.clause_id}": c for c in load_clauses()}


# --------------------------------------------------------------------------
# S11 - IRDAI non-payable list
# --------------------------------------------------------------------------


def parse_non_payable() -> list[dict]:
    """S11 - the excluded-consumables table into numbered entries.

    The table runs two number/item pairs per row. The serial number is kept so
    a verdict can cite "IRDAI-List-I #44" rather than just the name, and so the
    lookup helper can show which entry an item matched.
    """
    path = settings.policies_dir / NON_PAYABLE_FILE
    if not path.exists():
        log.warning("missing %s, non-payable list will be empty", path)
        return []

    items: list[tuple[int | None, str]] = []
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = [(c or "").strip() for c in row]
                    # Walk (number, item) pairs across the row.
                    for i in range(0, len(cells) - 1, 2):
                        name = cells[i + 1]
                        if not name or name.upper() == "ITEM":
                            continue
                        number = cells[i].strip()
                        items.append(
                            (
                                int(number) if number.isdigit() else None,
                                re.sub(r"\s+", " ", name.replace("\n", " ")).strip(),
                            )
                        )

    seen: set[str] = set()
    unique: list[dict] = []
    for number, item in items:
        key = item.lower()
        if key not in seen and len(item) > 2:
            seen.add(key)
            unique.append({"no": number, "item": item})

    # A wrapped item can leave its serial stranded on the next row. Fill from
    # the neighbour, but never reuse a number another entry already holds.
    used = {e["no"] for e in unique if e["no"] is not None}
    for position, entry in enumerate(unique):
        if entry["no"] is not None:
            continue
        before = unique[position - 1]["no"] if position else 0
        candidate = (before or 0) + 1
        while candidate in used:
            candidate += 1
        entry["no"] = candidate
        used.add(candidate)
    unique.sort(key=lambda e: e["no"])

    settings.non_payable_path.write_text(
        json.dumps(unique, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("wrote %d non-payable items to %s", len(unique), settings.non_payable_path)
    return unique


def load_non_payable() -> list[dict]:
    """Numbered IRDAI List I entries, cited as IRDAI-List-I #<no>."""
    if not settings.non_payable_path.exists():
        return []
    raw = json.loads(settings.non_payable_path.read_text(encoding="utf-8"))
    # Tolerate the older flat-list format.
    if raw and isinstance(raw[0], str):
        return [{"no": i + 1, "item": name} for i, name in enumerate(raw)]
    return raw


# --------------------------------------------------------------------------
# S8-S10 - indexes
# --------------------------------------------------------------------------


def clause_to_document(clause: Clause):
    from langchain_core.documents import Document

    return Document(
        # clause.text already opens with the title - prepending it again wasted
        # context and put a duplicated sentence in front of the cross-encoder.
        page_content=clause.text,
        metadata={
            "clause_id": clause.clause_id,
            "title": clause.title,
            "page": clause.page,
            "policy": clause.policy,
            "rule_type": clause.rule_type,
        },
    )


def build_vector_store(clauses: list[Clause], *, reset: bool = True):
    """S8/S9 - embed every clause and persist it in Chroma.

    Cosine space, because BGE vectors are normalised and cosine is what the
    model was trained for. Mixing in another embedding model later means
    rebuilding this from scratch - the vectors are not comparable.
    """
    from langchain_chroma import Chroma

    settings.db_dir.mkdir(parents=True, exist_ok=True)
    store = Chroma(
        collection_name=COLLECTION,
        embedding_function=_embeddings(),
        persist_directory=str(settings.db_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )

    if reset:
        existing = store.get(include=[])
        if existing["ids"]:
            store.delete(ids=existing["ids"])
            log.info("cleared %d existing vectors", len(existing["ids"]))

    documents = [clause_to_document(c) for c in clauses]
    ids = [f"{c.policy}:{c.clause_id}" for c in clauses]
    log.info("embedding %d clauses with %s", len(documents), settings.embedding_model)
    store.add_documents(documents=documents, ids=ids)
    log.info("vector store ready at %s", settings.db_dir)
    return store


def build_bm25(clauses: list[Clause]):
    """S10 - lexical index over the same clauses, held in memory.

    Not persisted: it rebuilds in well under a second, and a stale copy on disk
    that disagreed with Chroma would be a genuinely nasty bug to find.
    """
    from langchain_community.retrievers import BM25Retriever

    retriever = BM25Retriever.from_documents(
        [clause_to_document(c) for c in clauses], k=settings.bm25_top_k
    )
    log.info("BM25 index built over %d clauses", len(clauses))
    return retriever


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def run(*, force: bool = False, skip_index: bool = False) -> list[Clause]:
    settings.ensure_dirs()

    if settings.clauses_path.exists() and not force:
        clauses = load_clauses()
        log.info("loaded %d clauses from checkpoint %s", len(clauses), settings.clauses_path)
    else:
        clauses = build_clauses()
        save_clauses(clauses)

    parse_non_payable()

    if not skip_index:
        build_vector_store(clauses)
        build_bm25(clauses)

    return clauses


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the clause index from policy PDFs")
    parser.add_argument(
        "--force", action="store_true", help="re-parse and re-label, ignoring the checkpoint"
    )
    parser.add_argument("--skip-index", action="store_true", help="stop after clauses.json")
    args = parser.parse_args()

    setup_logging()
    clauses = run(force=args.force, skip_index=args.skip_index)

    from collections import Counter

    print(f"\nclauses: {len(clauses)}")
    print("by policy   :", dict(Counter(c.policy for c in clauses)))
    print("by rule_type:", dict(Counter(c.rule_type for c in clauses)))
    print("non-payable :", len(load_non_payable()), "items")


if __name__ == "__main__":
    main()
