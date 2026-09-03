"""Where the wall clock goes on one bill line, per backend.

Written because "the LLM was never the bottleneck" was an assertion, not a
measurement, and the numbers did not add up: three lines took five minutes on
Groq, which is 100s a line, against 11.3s a line measured locally on Ollama.
Reranking at 4.4s does not explain a gap that size.

This times one line end to end and splits it four ways:

    retrieval   search + sub-chunk + cross-encoder rerank
    api         time inside the model call itself
    limiter     time asleep waiting on the token bucket
    backoff     time asleep after a 429

Plus the number of judge attempts, since the agent retries a line it is not
confident about and a retry pays for retrieval a second time.

    uv run python eval/where_time_goes.py --backend groq
    uv run python eval/where_time_goes.py --backend ollama --no-cache
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import backends, llm
from core.config import settings
from core.logging_conf import setup_logging
from core.models import BillLine

# A line that has to be judged: not room rent (a table lookup, no model call)
# and not a non-payable item (the fast path, also no model call).
LINE = BillLine(item="anaesthetist charges", amount=14000.0, qty=1)
POLICY = "star_health"
SUM_INSURED = 300000.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["ollama", "groq"], default="groq")
    parser.add_argument("--item", default=LINE.item)
    parser.add_argument("--amount", type=float, default=LINE.amount)
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="measure a cold call; without this a cached line reports ~0s",
    )
    args = parser.parse_args()

    setup_logging()
    if args.no_cache:
        settings.llm_cache_enabled = False
    llm.use_backend(args.backend)

    # Import late: core.agent pulls retrieval, which loads two models.
    from core import agent as agent_module
    from core.ingest import load_clauses

    valid_ids = {c.clause_id for c in load_clauses() if c.policy == POLICY}

    retrieval_s = 0.0
    searches = 0
    real_search = agent_module.search

    def timed_search(*a, **kw):
        nonlocal retrieval_s, searches
        started = time.monotonic()
        try:
            return real_search(*a, **kw)
        finally:
            retrieval_s += time.monotonic() - started
            searches += 1

    # The embedding model and the cross-encoder load on first use, and that
    # load lands inside whatever call triggers it. Measuring it as if it were
    # per-line latency is how "retrieval takes two minutes a line" gets
    # believed. So it is paid first, and reported separately.
    warm_started = time.monotonic()
    real_search("room rent limit per day", POLICY)
    warmup = time.monotonic() - warm_started
    print(f"one-time model load and first search: {warmup:.1f}s")

    agent_module.search = timed_search
    backends.reset_stats()

    line = BillLine(item=args.item, amount=args.amount, qty=1)
    print(f"backend={args.backend} cache={'off' if args.no_cache else 'on'} line={line.item!r}")
    wall_started = time.monotonic()
    verdict, trace = agent_module.audit_line(line, POLICY, SUM_INSURED, valid_ids)
    wall = time.monotonic() - wall_started
    agent_module.search = real_search

    attempts = max((entry.get("attempt", 0) for entry in trace if "attempt" in entry), default=0)
    api = backends.STATS["api_s"]
    limiter = backends.STATS["limiter_wait_s"]
    backoff = backends.STATS["backoff_s"]
    other = wall - retrieval_s - api - limiter - backoff

    print()
    print(f"{'total wall clock':<22}{wall:>8.1f}s")
    print("-" * 30)
    for label, value in [
        (f"retrieval ({searches} search{'es' if searches != 1 else ''})", retrieval_s),
        (f"model calls ({int(backends.STATS['calls'])})", api),
        ("rate limiter asleep", limiter),
        (f"429 backoff ({int(backends.STATS['rate_limit_retries'])})", backoff),
        ("everything else", other),
    ]:
        share = (value / wall * 100) if wall else 0
        print(f"{label:<22}{value:>8.1f}s{share:>7.0f}%")
    print("-" * 30)
    print(f"{'judge attempts':<22}{attempts:>8}")
    print(f"{'allowed':<22}{verdict.allowed!s:>8}   clause {verdict.clause_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
