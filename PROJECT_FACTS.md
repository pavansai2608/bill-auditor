# Project facts

Raw material, not prose. Every figure here was read out of this repository on
**2026-09-06**. Where something could not be established from the repository it
says **uncertain** rather than guessing.

Two conventions used throughout:

- **measured** — a number produced by running something in this checkout today,
  with the command shown.
- **recorded** — a number read from a file in the repository that a past run
  wrote.

---

# 1. What the system does

## In plain language

**In:** a hospital bill as text, plus four inputs — the insurer (one of three),
the sum insured, the policy start date, and an optional "room limit as per your
policy schedule" which may be left blank.

**Out:** a line-by-line table. Every line carries what was charged, what the
policy allows, and **the clause id that caused the difference**. A line the
system cannot decide is flagged `needs_human` rather than guessed at.

**Who would use it and why.** Someone who has been handed a settlement letter
with deductions on it and no explanation of which policy term produced each one.
The insurer's own system produces the number; it does not produce the reasoning.
This produces the reasoning, and refuses to produce a number when it cannot
support one.

**What it is not.** It does not decide claims, it is not connected to an
insurer, and it has no authority. It is a reading of a document.

## The same thing, worked, on a real bill

`eval/bills/B01.json` — star_health, sum insured Rs 300,000, admitted
2026-03-12, discharged 2026-03-17.

The bill line, verbatim from the fixture:

```json
{"item": "Room Rent (Single A/C) 8,000 x 5 days", "amount": 40000.0, "qty": 5}
```

The clause it is matched to, `star_health II.1` ("In-patient Treatment"),
verbatim from `data/clauses.json`:

```
In-patient Treatment: We will cover the following Medical Expenses incurred in
respect of Hospitalization ...
i. Room, Boarding, Nursing Expenses all-inclusive as provided by the Hospital /
Nursing Home as per the limits given below;
[table] Sum Insured (Rs.) 1,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 2,00,000/- - Limit (Rs.) Up to 2,000/- per day
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 4,00,000/- - Limit (Rs.) Up to 5,000/- per day
[table] Sum Insured (Rs.) 5,00,000/- - Limit (Rs.) Single Standard A/C Room
```

The arithmetic, done in Python, never by the model:

```
sum insured 300,000  ->  table row "Up to 5,000/- per day"
eligible   = 5,000 x 5 days      = 25,000
allowed    = min(40,000, 25,000) = 25,000
deduction  = 15,000
```

**Final figure for that line: Rs 25,000 allowed against Rs 40,000 charged,
citing `star_health II.1`.**

That is not the end of the bill. Because the room breached its per-day cap, the
second pass computes:

```
ratio = eligible per day / charged per day = 5,000 / 8,000 = 0.6250
```

and applies it to the *associated medical expenses* on the same bill. The
Surgeon Fee line, charged Rs 80,000, becomes **Rs 50,000**, citing
`star_health I.Def45` — the definition of associated medical expenses, not the
room cap, because the cap says nothing about a surgeon's fee.

The answer key's own derivation for that line, verbatim from
`eval/answer_key.json`:

> `II.1 p10 table: Sum Insured 300,000 -> Up to 5,000/- per day; 5,000 x 5 = 25,000, min(40,000, 25,000) = 25,000`

The system reproduces the ratio. From the Eval stage of Jenkins `main #28`:

```
core.second_pass  second pass: ratio 0.6250 from 'Room Rent (Single A/C) 8,000 x 5 days',
                  rescaled 1 line(s) under II.1
```

**A note on which of these is evidence.** The key is written by hand from the
PDFs; the log line is the system's own output. They agree here. They do not
agree everywhere — that disagreement is the accuracy number in section 4.

---

# 2. Architecture

## Two deployments of the same code

`core/` is a library that imports no web framework. Two things wrap it:

1. **`api/`** — a single FastAPI process. This is what the eval and local
   development use, and it is a complete working system on its own. Kept
   deliberately; recorded as decision **D-10**.
2. **`services/`** — the same `core/` split into four containers.

Neither is a rewrite of the other. Both import the same `core/`.

## Every service

| service | what it does | talks to | holds in memory | container port |
|---|---|---|---|---|
| `gateway` | the only service a browser reaches. CORS, PII masking at the edge, request validation, job fan-out | `audit-service`, `ingestion-service` | the in-memory job store for its own requests | 8000 |
| `audit-service` | runs the LangGraph agent loop per bill line, the second pass, and all arithmetic | `retrieval-service` (over HTTP), Groq (primary), Ollama (fallback) | job store, LLM disk cache handle | 8000 |
| `retrieval-service` | dense + lexical search and the cross-encoder rerank | nothing outbound | ChromaDB collection, the BM25 index, the bge embedder and the bge reranker — all resident | 8000 |
| `ingestion-service` | PDF → clauses → embeddings. Runs on upload, and once at setup | Ollama (for clause labelling) | the embedder | 8000 |
| `frontend` | React SPA served by nginx | `gateway` | nothing | 80 |
| `ollama` | the local model server. In Kubernetes it is the **fallback**, not the default: it stays deployed and reachable at `http://ollama:11434` so a Groq refusal cannot end an audit | — | `qwen3:8b` weights | 11434 |

Published ports differ by deployment:

- **local monolith** — `uvicorn api.main:app` on **8000**, vite dev server on **5173**
- **docker-compose** — gateway `8000:8000`, frontend `5173:80`
- **kubernetes** — cluster-internal only; every Python service on 8000, frontend on 80
- **the Jenkins E2E stage** — `8100 + EXECUTOR_NUMBER` and `5100 + EXECUTOR_NUMBER`, because 8000 and 5173 belong to the compose stack on that agent

## The request path, in order

1. Browser submits the form in `frontend/src/components/BillForm.tsx`.
2. `POST /audit` to the gateway. Body: bill text, insurer, sum insured, policy
   start date, optional policy schedule.
3. Gateway masks PII (`core/masking.py`) **before anything is stored or
   prompted**, validates the policy against `/policies`, and creates a job.
4. Gateway returns **HTTP 202 with a `job_id` immediately.** An audit takes
   30–60 seconds; nothing waits on the socket.
5. The work runs in a `BackgroundTasks` worker thread. `api/jobs.py` is an
   in-memory store behind a lock. No database.
6. For each bill line, in parallel with a per-backend worker width (**D-12**):
   the LangGraph loop in `core/agent.py`.
7. After every line is judged, `core/second_pass.py` runs once for the bill.
8. `core/money.py` computes every rupee figure.
9. The browser polls `GET /audit/{job_id}` — `useAuditJob.ts` owns the polling —
   and receives `done`/`total` until the report lands.
10. `ReportView.tsx` renders the table, the trace, and the assumptions block.

## Where the LLM is called, and where it is not

**Called:**

- `classify` — which rule type this line is
- `judge` — read the three retrieved clauses, return a limit and a `clause_id`
- clause labelling at ingest time

**Not called — these are deterministic Python:**

- the non-payable fast path (`core/agent.check_non_payable`)
- the room-limit table lookup (`core/room_limit.py`)
- waiting periods (`core/waiting.py`)
- the proportionate second pass (`core/second_pass.py`)
- **every arithmetic operation** (`core/money.py`)
- all three guardrails

Every LLM call is cached to disk by a sha256 of the prompt (`core/llm.py`),
because the eval is re-run 50+ times.

---

# 3. The RAG pipeline, in detail

## 3.1 Ingestion: a PDF becomes clauses

Order of operations, from `core/splitter.py`:

```
PDF -> extract_pages -> clean_pages (drop furniture) -> split_clauses
    -> _split_definitions -> address-block trim -> attach_refs -> clauses.json
```

**The splitter cuts on clause numbers, never on character count.** A LangChain
text splitter is explicitly banned in this project: chopping every 800
characters loses the clause number, and a verdict that cannot name its clause is
worthless.

`CLAUSE_RE` is:

```python
r"^[ \t]*(\d+(?:\.\d+)*)\.?[ \t]+(?=\S)(.{0,120}?)[ \t]*$"
```

Five things the real PDFs forced, each found by failure:

**Two-column layout.** `star_health.pdf` is set in two columns and
`extract_text()` reads straight across, interleaving them into nonsense.
Columns are detected **per document by what fraction of text lines *begin* in
the right half** — star ≈ 0.41, the single-column documents ≈ 0.02–0.04, the
threshold `COLUMN_START_RATIO = 0.15`. Word-overlap heuristics near the page
centre do not separate these documents; line-start position does.

**Clause numbers restart per section**, so `1.1` is both "Standard Definitions"
and "Hospitalization Expenses" in hdfc_ergo. Ids are section-qualified —
`A.1.1`, `B.1.1`, `II.11` — which is also how the documents cite themselves.

**Split before joining wrapped lines, never after.** Joining first glues a
heading onto the sentence below it, the heading stops being its own line, and
the clause vanishes. This silently cut the yield to 88 clauses.

**Definitions blocks need a second pass.** hdfc_ergo's "Standard Definitions" is
one 16,000-character clause with 60+ terms numbered `Def. N.` inside it. Left
whole it swamps `num_ctx` and makes "Room Rent means…" uncitable, so it is split
again into `A.1.1.Def41`. `MIN_DEFS_TO_SPLIT = 5`.

**Star Health writes unnumbered definitions** as `Term: Term means …`, so
nothing before Section II matched the clause pattern and the whole definitions
section was being dropped — 68 definitions including the one that makes the
proportionate deduction reach the surgeon's fee. `UNNUMBERED_DEF_RE` recovers
them; `MIN_UNNUMBERED_DEFS = 10`.

### Tables

Table regions are removed from the flowing text and re-inserted **at the same
vertical position** as one labelled line per row, marked `[table]`:

```
[table] Sum Insured (Rs.) 3,00,000/- - Limit (Rs.) Up to 5,000/- per day
```

Four details, each found the hard way:

- **Cell geometry, not forward-fill alone.** A merged cell is one tall cell
  covering several rows; each row takes the cell whose vertical span contains
  its midpoint.
- **Word centres, not crops.** Cropping a cell catches the tail of the line
  above, putting `2,00,000/- 3,00,000/-` in one cell.
- **The header band.** Star Health rules its table from the second row down, so
  the header and first data row sit outside the detected table. The band above
  is read as part of it — `TABLE_BAND_LIFT = 48` points.
- **A data-table guard** (`is_data_table`). `find_tables()` also fires on prose
  layout boxes; without the guard, clause headings inside them are swallowed —
  **this cost 97 clauses.** Thresholds: `MIN_TABLE_ROWS = 3`,
  `MIN_TABLE_COLS = 2`, `MAX_DATA_CELL_CHARS = 80`,
  `MAX_PROSE_CELL_RATIO = 0.25`.

### The phantom space

`star_health.pdf` paints a space glyph **on top of** the first letter after a
list marker. The glyph has the same `x0`, `x1` and `top` as the character it
covers. Extraction therefore produced `E xpenses related to the treatment`.
Removed by `core/splitter.without_phantom_spaces`. **79 occurrences across 26
clause bodies and 6 titles.** Full story in section 9.

### The address-block trim

hdfc_ergo's ombudsman annexure is pages of postal addresses, detected by
`NOISE_RE` (`Tel.:|Email:|bimalokpal|cioins.co.in|Ombudsman`) at
`NOISE_HITS = 4`. It used to be dropped whole. It is now **cut after its last
address line**, because what follows it — with no heading between them — is
IRDAI List I and the plan-comparison grid that states every benefit limit in the
policy. Dropping the clause dropped those too: two pages, 6,314 characters,
sixteen rendered table rows.

### Why `hdfc_ergo E.2` stays whole

`E.2` is 12,414 characters: the plan-comparison grid plus the key that defines
what its "Not Covered" cells mean. Splitting it at the table/prose boundary was
**done in BA-240 and reverted in BA-242.** The measurement that settled it,
recorded in `ENGINEERING.md`:

- over nine queries the two halves came back together **twice**
- `QUERY_ANGLES["other"]` angle 1 returned the grid at rank 2 with the legend
  **nowhere in the top 25**, so no `rerank_top_n` widening recovers it
- `refs` is empty on both, so `with_references` has no citation to follow
- the legend names its target positionally — "Key to read **above table**" —
  which nothing can resolve once they are separate records

A judge handed the grid without the key reads "Not Covered" with no definition
of it, which is exactly how B21 and B28 produced a confident Rs 0 on lines the
key pays in full. The size is legal because `tests/test_ingest.py` caps **prose**
(2,666 against 12,000) and **total** (12,414 against 16,000) separately.

## 3.2 The index

Measured today:

```
uv run python -c "import json,collections; print(collections.Counter(c['policy'] for c in json.load(open('data/clauses.json'))))"
```

| policy | clauses |
|---|---|
| star_health | 152 |
| hdfc_ergo | 143 |
| niva_bupa | 104 |
| **total** | **399** |

Plus `data/non_payable.json`: **68 items** (the IRDAI List I of non-payable
items).

**`CLAUDE.md` states 402 clauses (153 / 144 / 105). That is stale.** The current
figure is 399. The difference is the flattened-table fix: `hdfc_ergo E.2.1` and
`E.3`, `star_health IV.22` and `IV.37`, and `niva_bupa 4.2.2` were removed as
table debris, and `hdfc_ergo E.2` and `star_health IV.31` were recovered.

**What is embedded:** the clause text, with the `[table]` rows in place. Long
clauses are additionally split into **sentence windows** before reranking, each
window carrying its parent's `clause_id` so citations still resolve.

| role | model |
|---|---|
| embeddings | `BAAI/bge-base-en-v1.5` |
| cross-encoder rerank | `BAAI/bge-reranker-base` |
| judge / classify (eval, CLI) | `qwen3:8b` via Ollama |
| judge / classify (API, and every service in Kubernetes) | `openai/gpt-oss-120b` via Groq |
| judge / classify (fallback, decided per call) | `qwen3:8b` via Ollama |

Vector store: **ChromaDB**, cosine. Lexical index: **rank-bm25**, in memory.

## 3.3 Retrieval — four stages, not two

| stage | value | setting |
|---|---|---|
| dense (Chroma, cosine) | top 20 | `chroma_top_k = 20` |
| lexical (BM25) | top 20 | `bm25_top_k = 20` |
| fusion (`EnsembleRetriever`) | 0.6 dense / 0.4 sparse | `dense_weight`, `sparse_weight` |
| sentence-window split | before rerank | — |
| cross-encoder rerank | **top 3** | `rerank_top_n = 3` |
| abstain below | 0.30 | `rerank_score_threshold = 0.30` |

**Why a lexical channel exists at all.** Policy documents are full of terms that
must match literally — "Aggregate Deductible", "Excl03", "Vasofix Safety" — and
embeddings blur exactly those.

**Why sentence windows.** Star Health states its per-day room rent table inside
a 1,500-character "In-patient Treatment" clause. Scored whole, the one relevant
sentence is drowned. `ClauseReranker` collapses windows back to one per clause
so the top 3 are three *distinct* clauses.

**Everything is filtered to a single policy.** A citation from the wrong insurer
is a fabricated citation.

### QUERY_ANGLES, and why there are three

`core/agent.py` holds one list of three phrasings per rule type. The retry loop
takes angle *n* on attempt *n*, capped at `max_attempts = 3`.

**Repeating a query that already missed is the one thing a retry must never
do.** The three angles are three different framings of the same need, not three
temperatures of the same query.

```python
QUERY_ANGLES: dict[RuleType, list[str]] = {
    "room_rent": [
        "room rent limit per day eligible room category",
        "proportionate deduction associated medical expenses room category exceeded",
        "boarding nursing expenses hospital accommodation entitlement",
    ],
    "sub_limit": [
        "{item} sub-limit maximum payable",
        "{item} limit per policy period per treatment",
        "benefit limit expenses payable for {item}",
    ],
    "waiting_period": [
        "{item} waiting period specified disease exclusion",
        "months of continuous coverage before this treatment is covered",
        "listed conditions excluded until expiry of waiting period",
    ],
    "copay": [
        "co-payment percentage of claim amount",
        "share of claim borne by the insured person",
        "deductible co-pay applicable to this policy",
    ],
    "non_payable": [
        "{item} excluded expense not payable",
        "non-medical items excluded from the claim",
        "items for which coverage is not available",
    ],
    "other": [
        "{item} limit coverage",
        "expenses payable for {item} during hospitalization",
        "{item} exclusion or cap under this policy",
    ],
}
```

There is a measured cost to a vague query, recorded in Phase 3: **the rerank
score tracks query specificity, the ranking does not.** "higher room category
pro-rata deduction" scores 0.58 against Niva Bupa; a fuller phrasing scores
0.98 — but clause 6.2.4 ranks first either way. Guardrail 5 keys off the
*score*, so a vague query can cause a false abstention. That is the agent's
problem to fix by rewriting, not the retriever's.

## 3.4 The agent loop

`core/agent.py`, LangGraph `StateGraph`. Nodes and edges as built:

```
START -> check_non_payable
           |-- hit  --> END            (zero LLM calls)
           `-- miss --> classify
classify -> room_limit
           |-- decided --> END          (zero LLM calls)
           `-- not     --> build_query
build_query -> retrieve -> judge -> grade
grade -> accept  --> END
      -> retry   --> build_query        (next angle)
      -> abstain --> abstain -> END
```

Node functions: `check_non_payable`, `classify`, `room_limit`, `build_query`,
`retrieve`, `judge`, `grade`, `abstain`.

**What makes it stop.** Three independent limits:

| limit | value | setting |
|---|---|---|
| attempts per line | 3 | `max_attempts = 3` |
| tool calls per line | 8 | `max_tool_calls = 8` |
| structured-output retries per call | 2 | `structured_output_retries = 2` |

and one hard stop: a **fabricated citation** never retries into acceptance — it
sets `state["fabricated"]` and the line abstains.

When the loop cannot decide, it sets `needs_human = True` with a reason. It
never guesses.

## 3.5 The deterministic paths

**The non-payable fast path** (`check_non_payable`). Runs first, before
classification, and costs **zero LLM calls**. It normalises the line item and
matches it against the 68 items in `data/non_payable.json`. A hit means the line
is allowed Rs 0 citing `IRDAI-List-I`. In the v9 recall measurement, **61 of 328
lines settled here and retrieval never ran.**

It carries one override: an item that the policy names as a *benefit* is not
zeroed by a List I name match. `BENEFIT_OVERRIDDEN_LIST_ITEMS` currently holds
`ambulance` — because List I item 67 is "Ambulance" while the policies grant a
road ambulance benefit. The override tests the **matched List I entry**, not the
bill line, so items 49 "Ambulance Collar" and 50 "Ambulance Equipment" stay
zeroed.

**The room-limit table lookup** (`core/room_limit.py`). Policy plus sum insured
reads the table row directly, with **no judge call**. `table_lookup` resolves
all nine star_health sums insured; pinned by
`tests/test_room_limit_golden.py`. Where the wording defers to the schedule
instead (`wording_lookup`), it says so rather than inventing a figure.

**Waiting periods** (`core/waiting.py`). Two dates and the period the clause
states, decided **before any line is judged**. A bill inside a waiting period
costs **zero model calls** — every line is nil, citing the waiting clause.

## 3.6 The second pass

`core/second_pass.py`. Runs once per bill, **after** every line is judged.

**Trigger:** any line whose verdict has `over_limit` set *and* which is a room
line by `ROOM_RE` (`room rent|room charges|bed charges|accommodation`).

```
ratio = eligible room rent per day / room rent actually charged per day
```

applied to every line that falls inside the policy's definition of associated
medical expenses.

Two rules that exist because breaking them produced wrong money:

- **Only a breached *room* line drives it.** `over_limit` is set by any breached
  per-day cap. An ICU line at 12,000/day against a 5,000/day limit once supplied
  a 0.4167 ratio and cut the surgeon's fee under a rule about a room the insured
  never breached. ICU is excluded from associated medical expenses by name.
- **Where more than one room line breached, the lowest ratio wins** — the
  insured cannot be better off for having been billed the same room twice.

Judging lines independently can never find this: nothing in the surgeon's-fee
line mentions room rent, yet one breached limit silently rewrites every other
line. **This is the point of the project.**

## 3.7 The three guardrails that exist

`core/guardrails.py` **is not built.** The guardrails live inline. Of the eight
originally planned, three are implemented.

**Guardrail 2 — fabricated citation.** `core/agent.py:457`:

```python
if output.clause_id not in state["valid_ids"]:
    state["fabricated"] = True
```

Rejects any `clause_id` not present in `data/clauses.json`, filtered to the
policy in hand. The eval tracks fabricated clauses as a metric that **must stay
at 0**, and it has been 0 in every recorded row.

**Guardrail 5 — rerank score below threshold.** In `agent.retrieve()`,
`agent.judge()` and `audit.py`. Below `rerank_score_threshold = 0.30`, nothing
retrieved is relevant enough to judge on, and the line abstains.

**Guardrail 3 — a room cap on a line the cap does not reach** (added in v7):

```python
def _room_cap_on_a_non_room_line(
    output: JudgeOutput, line: BillLine, candidates: list[RetrievedClause]
) -> bool:
    if not any(limit.basis == "per_day" for limit in output.limits):
        return False
    if ROOM_RE.search(line.item):
        return False
    cited = next(
        (c.clause for c in candidates if c.clause.clause_id == output.clause_id),
        None,
    )
    return cited is not None and governs_room_rent(cited)
```

Both halves are decided from the documents, never from the model's prose. It
fired on **19 line-attempts across 11 bills** and moved `room_rent_over` from
32.5% to 37.3%.

**Guardrail 3b — a limit of zero must be supported by the clause it cites**
(added in v11):

```python
def _unsupported_zero_limit(
    output: JudgeOutput, candidates: list[RetrievedClause]
) -> Clause | None:
    if not any(is_zero(limit) for limit in output.limits):
        return None
    cited = next(
        (c.clause for c in candidates if c.clause.clause_id == output.clause_id),
        None,
    )
    if cited is None:
        return None  # nothing to inspect; guardrail 2 owns that case
    return None if states_an_exclusion(cited) else cited
```

Measured across the 44 bills before it existed: **8 zero limits, every one
wrong**, 7 of them a confident Rs 0 on a line the key pays in full. It fired on
**4 verdicts and all 4 became correct lines.** Its limit is section 10 of
`KNOWN_LIMITATIONS.md`, reproduced in section 8 below.

## 3.8 Why the LLM never does arithmetic

`JudgeOutput` deliberately **has no `allowed` field.** The model returns a limit
plus a `clause_id`; `core/money.py` multiplies and subtracts.

The reason is stated in the repository as: 8B models are unreliable at
arithmetic, and **a wrong total is invisible** — it looks exactly like a right
one. A wrong *clause* can be checked against the index; a wrong sum cannot be
checked against anything.

`JudgeOutput.limits` is a `list[Limit]`, each with its own `basis`
(`per_day`, `per_hospitalization`, `per_policy_period`, `absolute`) and either a
rupee `amount` or a `percentage` of sum insured. `money.allowed_for_line`
resolves every limit for the bill in hand and takes the **minimum**. Three
separate fields could not hold what the wording says: `star_health II.8` states
"Rs.750/- per hospitalization **and** Rs.1,500/- per Policy Period" in one
sentence, and several benefits read "10% of Sum Insured **or** Rs 1,00,000,
whichever is less".

---

# 4. Every number

## 4.1 Every row in `eval/results.md`

Reproduced in order. **Scope matters more than any single figure here** — the
10-bill and 44-bill columns are different denominators and must never be
compared with each other.

| version | date | scope | lines | line acc | citation acc | payout err | abstention recall | false answers | dodges | fabricated | backend |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v0 | 2026-09-01 | **10 bills** | 82 | 24.4% | 22.2% | 52.8% | 62.5% | 3 | 42 | **0** | ollama (inferred) |
| v4 | 2026-09-01 | **10 bills** | 82 | 59.8% | 48.1% | 38.1% | 100.0% | 0 | 22 | **0** | ollama (inferred) |
| v5 | 2026-09-01 | **10 bills** | 82 | 68.3% | 56.8% | 44.0% | 100.0% | 0 | 21 | **0** | ollama (inferred) |
| v5-full | 2026-09-01 | **44 bills** | 328 | 59.5% | 51.9% | 41.1% | 71.4% | 8 | 90 | **0** | ollama (inferred) |
| v5-full (re-run) | 2026-09-01 | **44 bills** | 328 | 59.5% | 51.9% | 41.1% | 71.4% | 8 | 90 | **0** | ollama (inferred) |
| v5-full (re-run) | 2026-09-02 | **44 bills** | 328 | 59.5% | 51.9% | 41.1% | 71.4% | 8 | 90 | **0** | ollama (inferred) |
| 10+10 rerank candidates | 2026-09-02 | **10 bills**, tried and reverted | 82 | 68.3% | 56.8% | 44.0% | 100.0% | 0 | 21 | **0** | uncertain |
| v5-full (recorded backend) | 2026-09-02 | **44 bills** | 328 | 59.5% | 51.9% | 41.1% | 71.4% | 8 | 90 | **0** | ollama (qwen3:8b), cpu |
| v6 | 2026-09-02 | **44 bills** | 328 | 50.0% | 45.3% | 65.6% | 90.0% | 3 | 126 | **0** | ollama (qwen3:8b), mps |
| v6-cpu | 2026-09-02 | **44 bills** | 328 | 50.0% | 45.3% | 65.6% | 90.0% | 3 | 126 | **0** | ollama (qwen3:8b), cpu |
| v7 | 2026-09-02 | **44 bills** | 328 | 51.5% | 44.4% | 63.8% | 90.0% | 3 | 131 | **0** | ollama (qwen3:8b), cpu |
| ci-baseline-v7-quick | 2026-09-03 | **10 bills** | 82 | 56.1% | 46.9% | 76.0% | 100.0% | 0 | 32 | **0** | ollama (qwen3:8b), cpu |
| v8-key-audit | 2026-09-04 | **44 bills** | 328 | 51.5% | 44.4% | 63.8% | 90.0% | 3 | 131 | **0** | ollama (qwen3:8b), cpu |
| v9-phantom-spaces | 2026-09-04 | **44 bills** | 328 | 54.0% | 44.4% | 56.9% | 83.3% | 5 | 117 | **0** | ollama (qwen3:8b), cpu |
| v10-top5 | 2026-09-04 | **44 bills**, REVERTED | 328 | 47.3% | 46.9% | 69.6% | 60.0% | **12** | 108 | **0** | ollama (qwen3:8b), cpu |
| v11-zero-limit-guardrail | 2026-09-04 | **44 bills** | 328 | **55.2%** | 43.2% | 56.4% | 90.0% | 3 | 117 | **0** | ollama (qwen3:8b), cpu |
| v12-ambulance-override | 2026-09-06 | **44 bills** | 328 | 55.2% | 43.2% | 56.4% | 90.0% | 3 | 117 | **0** | ollama (qwen3:8b), mps |

**The current headline is `v11-zero-limit-guardrail`: 55.2% line accuracy over
44 bills / 328 lines.** `v12-ambulance-override` reproduces it to every decimal
place — the ambulance fix changed which lines were right, not how many.

**Rows v0 to v5-full are marked *inferred*, not recorded, for the Backend
column.** `core/backends.py` did not exist at tag v5; there was one code path
and it went to Ollama, so the backend is deduced from the code as it stood.
Every row after that records what actually answered.

### The version ladder is a different denominator

**v0 24.4% → v4 59.8% → v5 68.3%** is ten bills / 82 lines, held constant so
versions compare. It must never be joined to the 44-bill headline; the ten are
easier than the forty-four.

`eval/results.md` holds **no row for v2 or v3**, so the 51.2% and 54.9% that
appear in the ladder table of `PHASES.md` (lines 159–160) **are not reproducible
from it.** `PROGRESS.md`, which carried the same two figures, was removed.

### Three rows were withdrawn and re-run

Reasons recorded in `eval/results.md` rather than deleted:

- The first **v2** counted 18 correct `IRDAI-List-I` citations as fabrications —
  a scorer bug. Now pinned by `tests/test_eval_scoring.py`.
- The first **v3** took its proportionate ratio from any breached per-day cap,
  including an ICU line and a surgeon's fee — a second-pass bug. Now pinned by
  `OnlyRoomRentDrivesTheDeductionTest`.
- The first v3 row was re-run again after the ratio fix.

### The CI gate

The Jenkins Eval stage runs `--quick` (10 bills, 82 lines) against the
`ci-baseline-v7-quick` row of **56.1%**, at `--threshold 0.52` — just under
three lines below it. **It is a quick-subset number and must stay one.** The
previous gate of 0.65 was set against a run on an index later found to hold
corrupted tables.

Last measured value, Jenkins `main #28`: **0.585 PASS**.

## 4.2 Test count by module

**492 tests**, all passing. Measured locally with
`uv run python -m unittest discover -s tests`. Jenkins `main #28` recorded
`[INFO] Executed 478 unit tests`; `tests/test_cpu_quota.py` added 14 in BA-247.

| tests | file |
|---|---|
| 32 | `tests/test_backends.py` |
| 30 | `tests/test_api.py` |
| 29 | `tests/test_math.py` |
| 28 | `tests/test_services.py` |
| 25 | `tests/test_splitter.py` |
| 24 | `tests/test_retrieve.py` |
| 23 | `tests/test_eval_checkpoint.py` |
| 21 | `tests/test_zero_limit_guardrail.py` |
| 20 | `tests/test_second_pass.py` |
| 20 | `tests/test_prune_images.py` |
| 20 | `tests/test_hooks.py` |
| 20 | `tests/test_agent.py` |
| 19 | `tests/test_retrieval_cache.py` |
| 19 | `tests/test_ingest.py` |
| 19 | `tests/test_audit.py` |
| 18 | `tests/test_room_limit.py` |
| 15 | `tests/test_waiting.py` |
| 14 | `tests/test_cpu_quota.py` |
| 12 | `tests/test_workers.py` |
| 12 | `tests/test_room_cap_guardrail.py` |
| 12 | `tests/test_llm_cache.py` |
| 10 | `tests/test_text_bills.py` |
| 9 | `tests/test_example_report.py` |
| 9 | `tests/test_eval_scoring.py` |
| 9 | `tests/test_bill_readers.py` |
| 6 | `tests/test_tables_golden.py` |
| 5 | `tests/test_example_bill.py` |
| 4 | `tests/test_room_limit_golden.py` |
| 4 | `tests/test_index_coverage.py` |
| 4 | `tests/test_derive_key_divergence.py` |
| **492** | **total collected by `unittest discover`** |
| 4 | `tests/e2e/browser_flow.py` — **not** collected; run only by the E2E stage |

`tests/e2e/browser_flow.py` is deliberately not named `test_*.py`, because
PyBuilder matches on filename only and cannot exclude a directory, and
`run_unit_tests` would otherwise try to drive a browser.

## 4.3 Clause count by policy

| policy | clauses |
|---|---|
| star_health | 152 |
| hdfc_ergo | 143 |
| niva_bupa | 104 |
| **total** | **399** |

`data/non_payable.json`: **68 items.**

## 4.4 Retrieval recall

From `eval/recall_after.md`, 44 bills, clause index `b1a7b301cef9`, measured
after the phantom-space fix on 2026-09-04.

**recall@3 is the hard ceiling on citation accuracy.** The judge only ever reads
three clauses; a line whose answer is not among them cannot be got right, however
the model is prompted.

| scope | lines | recall@3 | recall@3 over 3 angles | recall@20 | in the candidate set |
|---|---|---|---|---|---|
| **all** | 261 | **34.5%** | **52.5%** | 72.4% | 72.4% |
| hdfc_ergo | 81 | 43.2% | 63.0% | 55.6% | 55.6% |
| niva_bupa | 74 | 40.5% | 56.8% | 94.6% | 94.6% |
| star_health | 106 | 23.6% | 41.5% | 69.8% | 69.8% |

| category | lines | recall@3 | recall@3 over 3 angles | recall@20 | in the candidate set |
|---|---|---|---|---|---|
| clean | 65 | 35.4% | 49.2% | 78.5% | 78.5% |
| non_payable | 41 | 36.6% | 43.9% | 61.0% | 61.0% |
| room_category_limit | 14 | 14.3% | 35.7% | 71.4% | 71.4% |
| room_rent_over | 75 | 37.3% | 72.0% | 72.0% | 72.0% |
| schedule_missing | 10 | 40.0% | 70.0% | 80.0% | 80.0% |
| sub_limit | 25 | 32.0% | 40.0% | 64.0% | 64.0% |
| waiting_period | 31 | 32.3% | 35.5% | 80.6% | 80.6% |

Lines retrieval never sees: **61** settled on the non-payable list, **6** the
key itself flags.

**recall@5 and recall@8 are not measured.** `eval/recall.py` reports three
depths — the raw candidate set, recall@20 and recall@3 — chosen because *where*
the ceiling bites decides what to fix. There is no recall@5 or recall@8 figure
in this repository, and inventing one from the v10 experiment would be wrong:
v10 measured recall **at the cut** with `rerank_top_n = 5`, which is a different
quantity.

**The three-angle candidate-set figure.** Two figures exist and they are not the
same:

- **52.5%** — recall@3 taken as the union over all three query angles, which is
  the ceiling the retry loop can actually reach. From `eval/recall_after.md`.
- **99.2%** — the candidate-set ceiling over the three angles, quoted in
  `ENGINEERING.md` against a recall@3 of 34.5%.

The per-scope table above shows "in the candidate set" as **72.4%** for a single
angle. **The 99.2% figure is not reproducible from `eval/recall_after.md`** and
its provenance is **uncertain**; it is reported here because `ENGINEERING.md`
states it, not because it was verified.

The conclusion the repository draws from these is: **the top-3 rerank cut, not
retrieval, is where accuracy is lost.**

## 4.5 Where the remaining errors are

Recorded in `ENGINEERING.md`:

| category | line accuracy | dodges |
|---|---|---|
| `room_rent_over` | 32.5% over 83 lines | 28 |
| `clean` | 38.5% | 38 |
| `sub_limit` | 34.6% | 16 |

Payout error is 65.6%, up from 41.1%, **because an abstention counts as zero in
the payout total** and there are 126 of them.

---

# 5. The CI/CD pipeline

`Jenkinsfile`, a **multibranch** pipeline. Jenkins 2.541.1, job `bill-audit`,
two executors on one macOS agent.

## What runs on which branch

| stage | any branch | `develop` | `main` |
|---|---|---|---|
| Checkout SCM | yes | yes | yes |
| Build | yes | yes | yes |
| Quality (Lint ∥ Unit) | yes | yes | yes |
| Eval | — | yes | yes |
| E2E | — | yes | yes |
| Docker | — | — | yes |
| Deploy | — | — | yes |
| Prune | — | — | yes |

The split is deliberate: `develop` stays quick, and loading five images into
minikube is minutes of work that only the release branch needs.

## Every stage, in order

| stage | what it runs | what it gates on |
|---|---|---|
| **Build** | `uv sync --frozen --all-extras`, `uv run pyb clean` | the lockfile resolves and the tree cleans |
| **Lint** | `uv run ruff check .`, `uv run ruff format --check .` | zero findings, zero reformatting |
| **Unit** | `uv run pyb --no-venvs run_unit_tests` | 492 tests pass |
| **Eval** | `uv run python eval/evaluate.py --quick --agent --second-pass --threshold 0.52` | line accuracy ≥ 0.52 on the 10-bill subset |
| **E2E** | `tests/e2e/run_stage.sh` | three ownership proofs, then 4 Selenium tests |
| **Docker** | five `docker build` invocations, tagged `:BUILD_NUMBER` and `:latest` | every earlier gate passed |
| **Deploy** | `k8s/deploy.sh` | every pod reports this build's tag |
| **Prune** | `ci/prune_images.py --build-number $BUILD_NUMBER` | every earlier gate passed |

Stages needing something a plain agent lacks — Ollama, a Docker daemon, a
cluster — **probe first and go `NOT_BUILT` with the reason** rather than
failing, because a stage that always fails teaches people to ignore red. The
exception is Eval on `main`, which is red rather than yellow: `main` is the
branch that deploys.

## The gate ledger, and why it is not `currentBuild.result`

Two `@Field` maps at pipeline scope:

```groovy
@Field Map<String, Boolean> gates = [:]
@Field Map<String, String> gateWhy = [:]

def gatePassed(String name)              { gates[name] = true }
def gateBlocked(String name, String why) { gates[name] = false; gateWhy[name] = why }
def blockers(List names) {
  return names.findAll { gates[it] != true }
              .collect { "${it} - ${gateWhy[it] ?: 'did not run'}" }
}
```

Each gate records, **as its own last act**, that it actually executed and
passed. `gatePassed('Eval')` is only reached if the evaluate command exited 0. A
stage that throws never reaches its `gatePassed()` call, so the ledger cannot
say a gate passed when it did not.

**Why not `currentBuild.result`.** `currentBuild.result` is null on a build
where a stage was *skipped*, and null is not a failure. A `NOT_BUILT` Eval
leaves the build green, and `main #21` built and tagged five images on a build
whose accuracy gate and browser tests had never executed. **"Not failed" is not
"passed". A gate that could not run has proved nothing.**

Docker checks `['Build', 'Lint', 'Unit', 'Eval', 'E2E']` explicitly by name.
Deploy adds `Docker`. Prune requires all seven.

`@Field`, not a bare assignment — a bare `gates = [:]` lands in the script
binding rather than pipeline scope and does not survive across stages.

**When Prune is blocked it does not `error()`.** The images are still correct
and still deployed; only the cleanup was withheld, and disk that was not
reclaimed is not a broken build.

## The E2E stage: three proofs

`tests/e2e/run_stage.sh` frees its ports and fails if it cannot, starts each
server as a **process-group leader** so cleanup can signal the group, and
refuses to run the test unless all three of:

1. **the process holding the port is in this run's process group**
2. **the bytes served carry this run's build stamp**
3. **the bundle was built against the API base this run is serving**
   (`frontend/dist/ba-build-base.txt`)

**No one of the three is enough.** The stamp cannot catch a survivor, because
Jenkins keeps its workspace and an orphan serves the same `dist/` this run just
rebuilt. The group check cannot catch a server that is ours but serving a
half-written `dist/`. Neither can catch a `BA_E2E_SKIP_BUILD` run, where the
stamp is written over a `dist/` this run never built and whose `VITE_API_BASE`
still points at whatever port the last real build used — on this agent, the
compose gateway on 8000.

**Do not replace any of them with a sleep or a retry.** A stale server answers
instantly, which is precisely why waiting longer never helped.

Ports are `8100 + EXECUTOR_NUMBER` and `5100 + EXECUTOR_NUMBER`, because
executor numbers are unique among builds running at the same time, which is the
property the collision needs. Verified on `develop #22`, which took 8101/5101 —
the non-zero offset is the evidence the variable reached the `environment` block
instead of collapsing to 8100.

## Image pruning rules

`ci/prune_images.py`. Four keep rules:

1. tag `latest`
2. tag `N` — the current build number
3. tag `N-1` — the previous build number
4. **any image referenced by a live deployment in the cluster, whatever its
   number**

Rule 4 is the one that is not arithmetic. The cluster does not necessarily run
what this build just pushed — before `k8s/deploy.sh`, a rollout could silently
not happen at all — so live references are read from the cluster at prune time
and **outrank the arithmetic**.

Three refusals, all of which exit 0 or 2 and delete nothing:

- **no `--build-number`** → `REFUSING TO PRUNE: no build number.` exit **2**.
  Without a build number the script has no idea which tags are current, and the
  earlier behaviour — protect only `latest` and the live refs — would have
  deleted every build the cluster had lost.
- **the cluster could not be read** → `REFUSING TO PRUNE: the cluster could not
  be read.` exit **0**. `cluster_images()` returns `None`, distinct from `[]`
  which means "read fine, nothing live".
- **a tag will not delete** → reported, exit **0**.

Images are deleted from **both** daemons. Docker Desktop's and minikube's are
separate, which is the same separation that made Deploy silently no-op.

## Deploy verification

`k8s/deploy.sh`:

1. refuse unless `kubectl`, `minikube` and `docker` are on PATH and `kubectl`
   reaches a cluster
2. refuse if any of the five images was never built
3. `minikube image load` each image
4. render the manifests through `sed`, substituting `:latest` → `:BUILD_NUMBER`,
   into a temp directory
5. one `kubectl apply`, then `kubectl rollout status` per deployment
6. **read the image back off every pod and exit 1 if any pod is not on this
   build's tag**

**It deploys the build-number tag because `:latest` cannot be verified.**
Comparing `:latest` against `:latest` passes whatever the pod is running — the
string never changes. Comparing image IDs across the two daemons does not work
either: `minikube image load` does not preserve the ID, so the same frontend
image is `f914d475731d` on the host and `cdc07a5959a2` on the node, and a load
that silently did nothing would still compare equal.

The manifests in git still say `:latest`; the rendering is done at deploy time
so there is one apply and one rollout, rather than an apply whose rollout is
immediately superseded.

`BA_DEPLOY_SKIP_LOAD=<service>` skips the image load for one service. It exists
to prove the script fails when an image does not reach the node.

## Stage timings from a green build

Jenkins `main #28`, `Finished: SUCCESS`, all eight stages. Timestamps read from
the build log; durations are first-to-last timestamped output within each stage.

| stage | start | end | duration |
|---|---|---|---|
| Build | 07:34:25 | 07:34:27 | ~1s |
| Unit | 07:34:28 | 07:35:23 | **55s** |
| Eval | 07:35:24 | 07:42:12 | **407s** (~6m 47s) |
| E2E | 07:42:13 | 07:42:34 | **21s** |
| Docker | 07:42:35 | 07:58:41 | **966s** (~16m 6s) |
| Deploy | 07:58:43 | 08:02:47 | **244s** (~4m 4s) |
| Prune | 08:02:48 | 08:03:10 | **22s** |
| Post Actions | 08:03:11 | 08:03:12 | ~1s |
| **total** | 07:34:25 | 08:03:12 | **~28m 47s** |

Lint has no timestamped output of its own — it runs in parallel with Unit inside
the Quality stage. Checkout SCM likewise.

In that build: `Executed 478 unit tests`, `PASS: line accuracy 0.585 meets the
threshold 0.520`, E2E `Ran 4 tests in 9.499s OK`, and
`Gates cleared: Build, Lint, Unit, Eval, E2E`.

## Three defects the first real CI runs found

- PyBuilder seeded its own venvs in two parallel stages and raced. Fixed with
  `pyb --no-venvs`, `pip` in the dev group, and moving Lint to ruff so the
  stages share no state.
- `run_unit_tests` collected the Selenium test, because PyBuilder matches on
  filename only. Renamed to `tests/e2e/browser_flow.py`.
- `services/ingestion/Dockerfile` copied `data/policies/`, which `.gitignore`
  excludes, so it could only ever build on the author's machine.

## Checkpoints are keyed on a fingerprint of the audit code

A sha256 over every `core/**/*.py`, the clause index, and the
`--agent`/`--second-pass` flags. Without it, a warm Jenkins workspace replayed
old reports and **a damaging commit passed the gate in one second.** Checkpoints
are filed under the fingerprint, so breaking accuracy costs a full re-run and
reverting is free.

## Tests must not read the ambient environment

`ContextDefaultsTest` passed locally and failed in CI because it read
`BA_LLM_BACKEND`, which the pipeline pins to `ollama`. Any test whose result
depends on a `.env`, an exported variable or a live backend is the same bug. The
suite is verified to pass with the environment stripped entirely.

---

# 6. Kubernetes and containers

## Manifests

| file | contains |
|---|---|
| `k8s/00-namespace.yaml` | Namespace `bill-auditor` |
| `k8s/01-config.yaml` | ConfigMap `bill-auditor-config` only. **No Secret** — see below |
| `k8s/templates/secret.example.yaml` | a template for Secret `bill-auditor-secrets`. Never applied: `deploy.sh` copies `k8s/*.yaml`, which does not recurse |
| `k8s/02-storage.yaml` | four PersistentVolumeClaims |
| `k8s/10-ollama.yaml` | Deployment + Service `ollama` |
| `k8s/20-ingestion-service.yaml` | Deployment + Service `ingestion-service` |
| `k8s/30-retrieval-service.yaml` | Deployment + Service `retrieval-service` |
| `k8s/40-audit-service.yaml` | Deployment + Service `audit-service` |
| `k8s/50-gateway.yaml` | Deployment + Service `gateway` |
| `k8s/60-frontend.yaml` | Deployment + Service `frontend` |
| `k8s/deploy.sh` | the deploy and verification script |
| `k8s/README.md` | operator notes |

## ConfigMap `bill-auditor-config`, in full

Every key in `k8s/01-config.yaml`. All are non-secret. `env_prefix = "BA_"` in
`core/config.py` maps each one onto a settings field.

| key | value |
|---|---|
| `BA_LLM_BACKEND` | `"groq"` |
| `BA_GROQ_MODEL` | `"openai/gpt-oss-120b"` |
| `BA_OLLAMA_BASE_URL` | `"http://ollama:11434"` |
| `BA_OLLAMA_MODEL` | `"qwen3:8b"` |
| `BA_NUM_CTX` | `"8192"` |
| `BA_TEMPERATURE` | `"0.0"` |
| `BA_KEEP_ALIVE` | `"30m"` |
| `BA_RETRIEVAL_URL` | `"http://retrieval-service:8000"` |
| `BA_AUDIT_URL` | `"http://audit-service:8000"` |
| `BA_INGESTION_URL` | `"http://ingestion-service:8000"` |
| `BA_AUDIT_WORKERS` | `"0"` |
| `BA_LOG_LEVEL` | `"INFO"` |
| `BA_CORS_ORIGINS` | `'["http://localhost:5173","http://localhost:3000"]'` |

`BA_LLM_BACKEND` is the one that decides the backend. Blank — which is the
default in `core/config.py` — falls through to per-context defaults (`api` →
groq, `eval` → ollama, `cli` → ollama); set explicitly to `groq` it applies to
every service in the cluster with no code change.

`BA_AUDIT_WORKERS` at `"0"` resolves to **2**, from the literal `return 2` in
`core.audit.worker_count()`. It does **not** vary by backend; `tests/test_workers.py`
pins 2 for both Groq and Ollama.

**`BA_TORCH_THREADS` is deliberately absent from this ConfigMap.** Left unset,
`core/cpu.py` reads the cgroup quota from `/sys/fs/cgroup/cpu.max` and derives
the thread count, so the CPU limit in the deployment is the only number that has
to be maintained. The setting exists to override that, for a test or a host
where the derivation is wrong.

## The Secret `bill-auditor-secrets`

**It is not declared in any manifest `k8s/deploy.sh` applies, deliberately.**
`kubectl apply` reconciles a Secret to whatever the manifest says, so a
committed Secret — even a commented placeholder — means every deploy wipes a
key that was put in the cluster by hand.

| | |
|---|---|
| key name | `BA_GROQ_API_KEY` (read by `groq_api_key: SecretStr`) |
| created | out of band, from `.env`, never committed |
| template | `k8s/templates/secret.example.yaml`, which `cp k8s/*.yaml` does not reach |
| consumed by | `ingestion-service`, `retrieval-service`, `audit-service`, `gateway`, each as `secretRef: { name: bill-auditor-secrets, optional: true }` |

`optional: true` is what lets a cluster with no Secret still start: the services
come up, Groq refuses on the first call, and `core/llm.py` falls back to Ollama.

## Deployments

| deployment | replicas | image | port | requests | limits |
|---|---|---|---|---|---|
| `ollama` | 1 | `ollama/ollama:latest` | 11434 | cpu 1, mem 6Gi | cpu 4, mem 10Gi |
| `ingestion-service` | 1 | `bill-auditor/ingestion-service:latest` | 8000 | cpu 500m, mem 1Gi | cpu 2, mem 3Gi |
| `retrieval-service` | 1 | `bill-auditor/retrieval-service:latest` | 8000 | cpu 500m, mem 1Gi | **cpu 4**, mem 2Gi |
| `audit-service` | 1 | `bill-auditor/audit-service:latest` | 8000 | cpu 1, mem 2Gi | cpu 3, mem 4Gi |
| `gateway` | **2** | `bill-auditor/gateway:latest` | 8000 | cpu 200m, mem 256Mi | cpu 1, mem 512Mi |
| `frontend` | **2** | `bill-auditor/frontend:latest` | 80 | cpu 50m, mem 64Mi | cpu 200m, mem 128Mi |

**Why `audit-service` and `retrieval-service` are 1 and not 2.** Both were
originally 2. Ollama's 6Gi memory *request* left no room on a single minikube
node for a second replica of either, and the pods would not schedule. Recorded
as **B-01**.

**Why `gateway` and `frontend` are 2.** They are small — 256Mi and 64Mi
requested — so a second replica fits, and they are the two that face a user.

**Why `retrieval-service` gets four cores and not one** (BA-248). It holds the
cross-encoder, which is ~99% of a search. At a limit of 1 it spent **99% of its
CPU scheduling periods throttled** — the quota was spent in the first few
milliseconds of each period and the threads waited out the rest. Measured on
the same image, same index, same pod spec with only the limit changing, five
real `/search` calls against a cold cache:

| limit | mean per search | periods throttled |
|---|---|---|
| cpu 1 | 85.14s | 99% |
| **cpu 4** | **24.37s** | **2%** |

**3.49x, and this pair is controlled.** An earlier profiling run recorded a
109s mean, and 109 → 24.37 would read as 4.47x — but the clause index moved
from 402 to 399 between the two, so **that comparison is not controlled and
4.47x is not a result.** Only the 3.49x figure above is.

Four rather than ten because a limit is not free: requests across the namespace
are 4,250m of the node's 10 cores, and the remaining headroom is what
everything else — ollama especially — expands into under load. Raising a
*limit* cannot affect scheduling, since the scheduler places pods by requests;
requests were not changed. The thread count follows the quota on its own
through `core/cpu.py`, so this one number is the only knob.

All five application deployments are **`maxSurge: 0, maxUnavailable: 1`**. The
node runs at ~92% of its memory requests, so a surge pod cannot schedule and the
rollout hangs — one `retrieval-service` pod had been Pending for 17 hours from
exactly this. Stop first, then start. Surging buys nothing on one node.

## PersistentVolumeClaims

| PVC | size | used by |
|---|---|---|
| `ollama-models` | **12Gi** | ollama — the `qwen3:8b` weights |
| `clause-data` | 2Gi | ingestion (write), retrieval, gateway (read) |
| `llm-cache` | 2Gi | audit-service — the prompt-hash disk cache |
| `retrieval-cache` | 2Gi | retrieval-service |

## How images reach minikube

**They do not, by themselves.** Jenkins builds into Docker Desktop's daemon;
minikube runs its own daemon inside the minikube container and cannot see across.
Every image must be carried over with `minikube image load`, which `k8s/deploy.sh`
does for all five before applying anything.

This is one of the three defects that made Deploy a no-op for two days. The
others: every manifest pinned `:latest`, so the Deployment spec was byte-identical
from one build to the next and `kubectl apply` started no rollout at all; and
`imagePullPolicy: IfNotPresent` then ensured even a restarted pod kept the image
it already had. The pods on 2026-09-05 were created `2026-09-03T15:23:44Z`;
build 22 had finished an hour earlier and had never reached the cluster.

## What the rollout verification checks

1. every one of the five images exists in the host daemon at `:BUILD_NUMBER`
2. `minikube image load` succeeded for each
3. `kubectl rollout status deploy/<name>` completes within the timeout, for each
4. **the image read back off every running pod is on this build's tag** — exit 1
   otherwise

Step 4 is the one that matters. `rollout status` exits 0 on a Deployment nobody
changed, which is exactly how this passed for two days.

## Container images

| image | base | final base | port |
|---|---|---|---|
| `bill-auditor/gateway` | `python:3.14-slim` (builder) | `python:3.14-slim` | 8000 |
| `bill-auditor/audit-service` | `python:3.14-slim` | `python:3.14-slim` | 8000 |
| `bill-auditor/retrieval-service` | `python:3.14-slim` | `python:3.14-slim` | 8000 |
| `bill-auditor/ingestion-service` | `python:3.14-slim` | `python:3.14-slim` | 8000 |
| `bill-auditor/frontend` | `node:22-alpine` (builder) | `nginx:1.27-alpine` | 80 |

All five are multi-stage. Healthchecks:

- gateway, audit — `/health`, interval 30s, timeout 5s, **start-period 90s**
- retrieval, ingestion — `/ready`, interval 15s, timeout 10s, **start-period 180s**
  (they load two transformer models before they are useful)
- frontend — `wget -qO- http://127.0.0.1/`, interval 30s

The frontend healthcheck probes `127.0.0.1`, not `localhost`, because nginx here
is IPv4-only and `localhost` resolved to `::1`.

**Dependency extras exist to keep images small.** Installing everything in all
four Python images cost **8.82 GB each** — the same torch, the same CUDA wheels,
four times over, for two services that never embed anything. `pyproject.toml`
splits `agent`, `retrieval` and `ingestion` extras, and pins torch to the CPU
wheel index: PyPI's linux torch is the CUDA build and drags `nvidia-*` (2.9 GB)
and `triton` (650 MB) into an image whose only job is a 400 MB embedding model
on a CPU.

**The embedding weights ship in the image; the LLM does not** — decision
**D-13**. The builder stage runs
`SentenceTransformer('BAAI/bge-base-en-v1.5')` and deletes the `.onnx`, `.h5`,
`.msgpack` and `.ot` duplicates, then the runtime stage proves the model loads
offline.

## docker-compose

Six containers: `ollama`, `ingestion-service`, `retrieval-service`,
`audit-service`, `gateway`, `frontend`. Published: gateway `8000:8000`,
frontend `5173:80`. Four named volumes matching the four PVCs.

Verified end to end on 2026-09-01: all five images build, all six containers
report healthy, B01 audited through the gateway. Four defects it found that
syntax checking could not — the four Python images could not build at all
(`-e .` in `requirements.txt` with no `src/` in the builder stage); ingestion had
no Ollama URL so **all 402 clauses were labelled `other`**; the frontend
healthcheck probed `localhost` against an IPv4-only nginx; and `qwen3:8b` was
OOM-killed in a 7.7 GB VM. Recorded as **B-02**.

---

# 7. Testing

Framework: **PyUnit (`unittest`)**, not pytest — Jenkins drives it through
PyBuilder (`pyb run_unit_tests`). 492 tests, ~82 seconds locally. The 55s CI
figure was measured at 478 tests and has not been re-measured since.

Full per-file counts are in section 4.2.

## The unusual ones

### `tests/test_index_coverage.py` — the index coverage guard (4 tests)

Asks the question no other test asked: **is the content still there?**

Per policy it asserts that the indexed character count and the set of source
pages reaching the index have not shrunk, with today's numbers pinned in
`tests/fixtures/index_coverage.json`. Both are **floors, not equalities** —
growth passes.

**What it would catch, and did.** A one-line change to `_region_text` removed
flattened table debris from `hdfc_ergo E.2.1` and, in the same stroke, deleted
pages 50 and 51 of that document: **6,314 characters, a 16-row plan-comparison
grid, and the legend defining what "Not Covered" means in it.** All 462 unit
tests passed. All 6 golden table tests passed. Nothing could see it, because
every other test asks whether what is there is correct and none asks whether it
is still there.

Page coverage is measured **by content, not by `Clause.page`**: each page is
pinned as a 30-character probe — a line of that page squashed to bare
alphanumerics. Squashing is what survives `join_wrapped_lines`. A clause
legitimately merging into one that starts on an earlier page still passes; what
fails is content that is nowhere at all.

It reads `data/clauses.json`, **not the PDFs**, because `data/policies/*.pdf` is
gitignored and the module previously raised `FileNotFoundError` nine times out of
nine in Jenkins while passing locally. There is deliberately **no `--update`
flag**.

### `tests/test_tables_golden.py` — the golden table tests (6 tests)

Stores the exact extracted text of the eight rule-bearing table clauses under
`tests/fixtures/tables/` and fails on any diff. It splits straight from the
PDFs, so it tests the **splitter** rather than the checkpoint — and therefore
skips in CI with `policy PDFs not present`.

The eight pinned clauses: `star_health II.1`, `II.5`, `II.20`, `II.8`,
`hdfc_ergo B.1.1`, `B.1.1.1`, `E.1.6`, `niva_bupa 6.2.4`. Plus a broad net over
**every table in every document**, because pinning one clause and leaving the
rest loose is what let `II.5` sit in the index with a column heading where nine
sub-limits should have been — and `II.5` was on the list. The *fixture* was
wrong, frozen from a bad read.

**What it would catch.** It exists because this code broke three times and
**every break was silent** — the output still looked like text, so nothing
failed and the damage only showed when someone read a clause by eye. One of
those breaks put `5,00,000` next to a limit belonging to the 3L and 4L rows.

Regenerate deliberately with `uv run python tests/test_tables_golden.py --update`,
after reading the diff. Regenerating without reading it is how the fourth
regression gets in.

### `tests/e2e/browser_flow.py` — the E2E ownership proof (4 tests)

Selenium 4. Run only by `tests/e2e/run_stage.sh`, never by `unittest discover`.

**What it would catch.** Not a broken frontend — the three proofs in the stage
script catch something the tests cannot: that the browser is being pointed at
*this build*. Before them, `develop #17` failed because Selenium drove a stale
bundle, and `main #11` **passed** after its own preview server died with "Port
5173 is already in use". Green and red for the same wrong reason.

### `tests/test_zero_limit_guardrail.py` — the zero-limit guardrail (21 tests)

Three classes: what counts as an exclusion, where the guardrail must fire, and —
as many tests again — **where it must not**. Blocking an honest zero loses a
correct line, so `TheGuardrailStaysQuietTest` is the half that protects
`star_health II.20`, whose benefit table says "Not Available" and whose zero is
correct.

It pins the clauses the eval's eight wrong zero limits were read from, and
asserts `hdfc_ergo E.2.1` is **no longer in the index at all** — so guardrail 2
rejects those citations before guardrail 3 is ever asked.

**What it would catch.** A regression that puts a flattened table clause back
into a citable index, or a widening of `EXCLUSION_RE` that starts rejecting
honest zeros.

### `tests/test_example_report.py` — the example-report test (9 tests)

`frontend/src/data/exampleReport.json` is a real v11 B01 checkpoint, exported by
`eval/export_example_report.py`, and it is what the GitHub Pages build renders
because there is no API on a CDN.

**What it would catch.** It pins every citation in that committed file against
`data/clauses.json`. **A fabricated citation in a committed file is not covered
by the metric that keeps fabrications at zero everywhere else** — that metric
measures runs, not fixtures. Without this test, the one screen most people would
ever see could show a clause id that does not exist.

### Others worth naming

- `tests/test_room_limit_golden.py` (4) — pins the room entitlement resolved for
  all nine star_health sums insured. Written while ruling `room_limit.py` out as
  the cause of the v6 drop.
- `tests/test_derive_key_divergence.py` (4) — pins the divergence between
  `eval/derive_key.py` and the answer key. `--write` is refused because it would
  revert 87 recorded decisions.
- `tests/test_eval_scoring.py` (9) — exists because the first v2 row counted 18
  correct `IRDAI-List-I` citations as fabrications.
- `tests/test_prune_images.py` (20) — includes
  `test_without_a_build_number_nothing_of_ours_is_nominated`, which replaced an
  earlier test that had pinned the *dangerous* behaviour.
- `tests/test_hooks.py` (20) — tests the git hooks themselves.

---

# 8. What it gets wrong

## 8.1 The retrieval finding: the Associated Medical Expenses definition

From `eval/recall_after.md`: **124 of 261 retrievable lines are missed by every
one of the three query angles.** Counting which clause each miss wanted:

| clause the key cites | misses | what it is |
|---|---|---|
| `star_health I.Def45` | **31** | Associated Medical Expenses — definition |
| `niva_bupa 6.2.4` | **31** | the pro-rata formula for a higher room category |
| `star_health II.1` | 21 | in-patient treatment, the room rent table |
| `hdfc_ergo A.1.2.Def5` | **20** | Associated Medical Expenses — definition |
| `star_health III.2` | 10 | specified disease waiting period |
| `hdfc_ergo C.1` | 9 | waiting period |
| `niva_bupa 5.1.2` | 1 | — |
| `hdfc_ergo B.1.1` | 1 | room rent "At Actuals" |

**51 of the 124 misses — 41% — want an Associated Medical Expenses definition**
(`I.Def45` plus `A.1.2.Def5`). Add `niva_bupa 6.2.4`, which is the same idea
expressed as a formula rather than a definition, and it is **82 of 124, 66%.**

The miss table marks these `not retrieved at all`, meaning the clause was not in
the reranked list **at any depth** — a candidate-set problem, not a ranking one.

### Why no bill-line query can find it — measured

The repository records the counts but not a reason, so this was measured today
against the live index:

```
uv run python -c "from core.retrieve import search; ..."

Medicines and Drugs limit coverage                    -> top3 ['II.16','I.Def55','III.1']   I.Def45: NOT IN LIST
expenses payable for Medicines and Drugs during hosp. -> top3 ['II.7','II.25','II.8']       I.Def45: NOT IN LIST
Surgeon Fee limit coverage                            -> top3 ['I.Def55','II.17','II.16']   I.Def45: NOT IN LIST
associated medical expenses definition nursing OT     -> top3 ['I.Def45','II.1','I.Def41']  I.Def45: rank 1
```

The first three are `QUERY_ANGLES["other"]` angles 1 and 2 with real B01 line
items substituted. **The clause is perfectly retrievable — rank 1 — from a query
that names the concept. It is unreachable from every query derived from the bill
line.**

The mechanism: the query is built from the line item, and the relationship
between the line and the clause is not a similarity. `I.Def45` is cited for
"Medicines and Drugs" precisely **because that line falls *outside* the
definition** — the clause reads "does not include cost of pharmacy and
consumables". A query about medicines cannot find a clause whose relevance is
that it excludes medicines. For "Surgeon Fee" the clause does name surgeons, but
as one item in a definition of a category, and the surrounding text is about the
category boundary rather than about surgeons.

**This is the largest single identified block of retrieval loss in the project**
and it is not a ranking problem, a threshold problem, or a model problem. No
value of `rerank_top_n` fixes it: v10 raised the cut to 5, recall at the cut rose
34.5% → 44.4%, and accuracy **fell** to 47.3%.

## 8.2 `KNOWN_LIMITATIONS.md`, reproduced in full

Everything below is the file verbatim, with heading levels shifted down two so
it nests inside this document. Nothing else is changed.

### Known limitations

What this system gets wrong today, in plain language.

**What the system does, in one line:** you give it a hospital bill and a
policy; it goes through the bill line by line and says how much the insurer
should pay for each line, quoting the exact policy clause that decided it. If
it cannot find a clause, it flags the line for a human instead of guessing.

---

#### 1. It flags lines that should simply be paid in full

**Example.** Bill B03 is a cataract operation on a Niva Bupa policy. Six lines:
the room, the surgery package, the lens, the surgeon, medicines, tests. The
correct answer is that all six are paid in full - this policy puts no cap on
any of them.

The system flags five of the six and says "I could not find a clause."

**Why.** For each line the system searches the policy for a clause that *limits*
that line. Two results are possible:

- it finds a limit, e.g. "ambulance is capped at Rs 750" → it applies the cap
- it finds nothing → it flags the line

The problem is that "nothing" has two very different meanings:

| What is true | What the system sees |
|---|---|
| There is no cap, so pay the full amount | nothing found |
| There is a cap and the search missed it | nothing found |

It cannot tell these apart, so it plays safe and flags. For the lens line, the
best clause it found scored 0.02 out of 1 for relevance - effectively nothing
in the policy is about intraocular lenses, because nothing limits them.

**Why this is not a quick fix.** The system would have to ask a different
question: not *"what limits this line?"* but *"is this line covered at all?"*
That means changing what the AI model is asked to return, and changing what
counts as an acceptable answer. The danger is the direction it fails in. Today
a missed clause becomes a flag, which a human then checks. After such a change,
a missed clause could become "no limit found, pay in full" - the system would
quietly overpay and nobody would notice. That trade needs its own testing
before it goes in.

**So for now:** flagging is wrong, but it is wrong in the safe direction. A
flagged line gets looked at by a person. A wrongly paid line does not.

---

#### 2. Star Health bills are not checked against the 24-month disease list

**Background.** Health policies do not cover certain planned operations -
cataract, hernia, knee replacement and similar - until you have held the policy
for 24 months. This is called a *waiting period*. If someone claims for a
hernia four months into their policy, the insurer pays nothing.

To apply that rule the system needs two things from the policy document: the
period (24 months) and the list of conditions it applies to.

**The problem.** For Star Health, the list is missing. Its clause III.2 states
the 24 months and then ends with the words *"f. List of specific
diseases/procedures;"* - the list is on the following page of the PDF and did
not survive the text extraction. HDFC Ergo and Niva Bupa both have their lists
inside the clause text, so they work fine.

**What the system does about it.** It refuses to apply the rule unless it can
actually see the condition named in the policy's own text. So a Star Health
hernia claim inside the waiting period will be paid rather than excluded.

That is a mistake, but the alternative is worse: zeroing an entire hospital
bill based on a list the system cannot read, while displaying a clause number
that makes it look verified.

**Fix.** Find where that list ends up when the PDF is split into clauses and
attach it to III.2. Roughly half a day, mostly in the PDF-splitting code.

---

#### 3. It never applies the pre-existing disease rule

Policies also exclude conditions you already had before buying the policy,
usually for 36 months. The system reads that rule and reports it, but never
applies it.

**Why.** Nothing on a hospital bill says whether a condition existed before the
policy started, and nothing the user types into this system says so either. The
only way to apply the rule would be to assume the answer. So the system records
the rule and the clause in its notes, and leaves the judgement to the human
reviewer who has the medical history.

---

#### 4. The version-to-version numbers come from 10 bills, not all 44

The whole set has now been run: **59.5% line accuracy over 44 bills and 328
lines**, recorded in `eval/results.md` as `v5-full - 2026-09-02`. That is the
number to quote.

The v0 to v5 comparison rows are still the `--quick` setting, which runs the
first 10 bills (82 lines), because a full run takes around 45 minutes and that
is too slow to sit between one version and the next. The subset is held constant
so a change between two versions is attributable to the change rather than to a
different sample.

**Why this matters when reading the numbers.** The two are different
denominators and must not be put on one ladder: v5 scores 68.3% on the ten and
59.5% on the forty-four, because the other 34 bills are harder. And on the
subset some categories hold only 6 or 7 lines, so one line moves that category
by 14 percentage points. Treat small category swings there as noise.

#### 5. Ten bills still need a person to check the answer key

`eval/answer_key_provenance.md` lists ten bills whose derivations need checking
against the source PDFs by a human, and **that check has not been done.** The
key was written by a language model reading policy documents and the judge is
also a language model reading policy documents; reading whole pages by a
separate route removes the shared plumbing but not the shared reader. The same
file records an unresolved conflict on B43 - whether HDFC's "At Actuals" is a
stated default or a deferral to the schedule - which needs a decision before
that bill's row means anything.

#### 6. The eval measures agreement between two implementations, not correctness

This is the most serious limitation in the file, and it is not about a category
or a bill. It is about what the headline number means.

**The key's substance came from a model reading the same PDFs the judge reads.**
`eval/derive_key.py` is genuinely independent of the pipeline's *plumbing*: it
imports no retriever, no judge, no audit code, and it makes no model call. That
is real, and it is the failure most eval harnesses have. But it is independence
of the wiring, not of the reading. Every policy figure in it - the room-rent
table, the cataract sub-limits, the definition of associated medical expenses,
the 24-month list - is a constant typed into the source file, put there by a
language model reading the three policy documents. The judge is a language model
reading the same three documents. Different route, same reader. A misreading
available to one was available to the other, and **nothing re-checks either
against the PDF.**

Worth being exact about: `derive_key.py` does not open the PDFs. Its whole
runtime input is `eval/bills/*.json` and `data/non_payable.json`. The docstring's
claim that rules were "read off the PDF pages directly with pdfplumber"
describes where the constants came from when someone wrote them, not what the
script does. It imports `argparse, json, re, sys, datetime, pathlib`, and
nothing else.

**The key and `core/` share a taxonomy.** This is the part that cannot be fixed
by being careful. The key decides that a surgeon's fee is an associated medical
expense with its own `AME_RE`; `core/second_pass.py` decides the same thing with
its own `AME_RE`. The key routes room lines with `ROOM_RE`; `core/agent.py`
routes them with `RULE_PATTERNS`. Two separate regex sets, written by the same
process, cutting bill lines into the same categories with the same vocabulary.

Where that cut is wrong, **both sides are wrong in the same direction and the
eval scores the line correct.** No amount of running the eval can surface it,
because the eval is the thing that shares the error. Only reading the policy can.

**So what the number is.** 51.5% line accuracy is a real, deterministic,
reproducible measurement of how often the pipeline agrees with a second
implementation of the same beliefs. It will catch a regression in the splitter,
the retriever, the reranker or the judge - that is what it is for, and it has
done so more than once. It will not catch a misreading of the policy. Read it as
*agreement*, not as *correctness*, and do not describe it as accuracy against
the documents anywhere it could be mistaken for one.

**What is on the correct side of that line.** Exactly two things.
`eval/build_answer_key_review.py` goes back to the PDFs and locates quoted text
on real pages; it prepares a check by a person, and that check has not been
performed. And `tests/test_tables_golden.py` pins the extracted text of every
table in all four documents, which is the one place a policy figure is verified
against the source rather than against a second opinion about the source.

`eval/answer_key_todo.md` is the shortlist that would close the gap: **72 rows
in 5 questions**, each one naming the page to open.

##### What was checked, and what it showed

`eval/repair_answer_key.py` takes the text each derivation puts in quotation
marks and searches every clause of that policy for it. Where exactly one clause
contains every quote, that clause is the citation. It never reads a verdict, a
report or a checkpoint.

It moved **nothing**. Of 261 cited lines, 189 already point at a clause that
contains every quote they use; 59 are table derivations with no quoted text to
search for; 13 quote text that is in no clause of their policy at all.

Those 13 are one question. Every one cites `star_health III.2`, the
specified-disease waiting period, and quotes *"Expenses related to the treatment
of the listed conditions"*. That text is in `hdfc_ergo C.1` and `niva_bupa 5.1.2`
but not in star_health's own III.2 - whose indexed text begins **"E xpenses
related to the treatment of the following listed Conditions"**. The split word
is a PDF extraction artefact; there are **48 of them across 33 clauses**, and
BM25 cannot match a term that is broken in half. The citation is probably right
and the evidence chain is broken, which is a different problem from a wrong
citation and needs the same PDF to settle.

The "37 of 93 entries cite a clause that does not contain the text they quote"
figure in `answer_key_review.md` is **stale**. Those rows were the associated
medical expenses citing the room-rent cap, and decision D-12 moved 85 of them by
hand to `I.Def45` / `A.1.2.Def5` - which is exactly where their quotes live. The
repair found nothing because the repair had already been made as a decision.

**`eval/derive_key.py` no longer reproduces the key**, and running it with
`--write` would have reverted 87 of those decisions in one command. `--write` is
now refused, and `tests/test_derive_key_divergence.py` pins the disagreement
line by line against a golden file so it cannot grow unnoticed.

#### 7. A fabricated figure attached to a real clause passed every check

Until v11 the system could tell an insured that an expense was not payable,
cite a real clause for it, and nothing anywhere would notice.

The guardrail that exists to stop invented citations - guardrail 2 - asks one
question: is this clause id in the index? `star_health II.1` is. It is the
in-patient coverage clause, and it opens *"We will cover the following Medical
Expenses"*. On B41 and B42 the judge returned a limit of **Rs 0** citing it, for
anaesthetist charges. `money.allowed_for_line` did exactly what it is built to
do and returned zero. The report showed Rs 26,000 struck out, with `II.1` beside
it as the authority.

**Every check passed.** The clause was real, the model was confident, the
arithmetic was correct, and the citation resolved to a clause a reader could
look up and find. The only thing wrong was that the clause did not say it.

Measured across the whole 44-bill eval: **8 zero limits, all 8 wrong**, 7 of
them landing as a confident `Rs 0` on a line the answer key pays in full.

The gap was structural, not a slip. The project's hard rule is that the model
never does arithmetic - it reports a limit and a clause id, and Python computes
the money. That removes one class of error entirely and, until now, quietly
assumed the *limit* was as trustworthy as the arithmetic. It is not. The clause
id was checked against the index from the start; the figure attached to it was
checked against nothing.

**What v11 closes, and what it does not.** A limit of zero is now rejected
unless the cited clause contains exclusionary language, because zero is not a
small number - it is the claim that the policy excludes the expense, and it is
the most damaging thing this system can say short of citing a clause that does
not exist. Every other figure is still unverified. A limit of Rs 5,000 read out
of a clause that states Rs 50,000 would pass today exactly as the zero did.

And three of the eight still get through, for a reason worth stating plainly:
`hdfc_ergo E.2.1` is headed "Not Covered" and `star_health II.20` says "Not
Available" in its benefit table, so both satisfy a rule that only asks whether
the clause excludes *anything*. Neither excludes the line being judged. Closing
that needs the exclusion tied to this expense, which is the general case - and
the general case is where false rejections start costing correct answers.

The honest summary: **the citation is verified, the figure is not, and only the
worst figure is.**

#### 8. Until 2026-09-04, Jenkins E2E results did not test the build under test

Every E2E result this project has recorded — **including the green ones** — was
produced against whatever happened to be listening on port 5173. That was
usually a `vite preview` orphaned by an earlier build.

The stage started its servers in the background, polled `curl -sf
http://localhost:5173` until something answered, and killed `$!` afterwards.
Three things were wrong with that and they compounded:

- `npx vite preview` forks vite as a child, so `kill $!` killed the wrapper and
  left the server holding the port. Every build donated one orphan to the next.
- The readiness check asked whether *something* answered, never whether it was
  ours. An orphan answers in milliseconds, so the check always passed
  immediately — the faster it passed, the more certainly it was wrong.
- The preview server ran inside a background subshell, so when it failed to
  start the failure went nowhere.

`develop #17` failed because Selenium drove a stale bundle that had no
`[data-testid='bill-text']`. `main #11` passed after its own preview server died
with "Port 5173 is already in use". Same defect, opposite colours, and neither
number meant anything.

**What that costs retrospectively.** No E2E run before this fix is evidence of
anything. A green E2E stage in an old build does not mean the frontend worked
then; it means something was listening. The four tests are real and they do pass
against a fresh build — verified 2026-09-04, twice in a row, 4 tests in ~6s —
but that is a statement about today, not about the build history.

**What is still not covered.** The fix proves the server is this run's process
*and* serving this run's build stamp, which is as far as process identity can be
taken. It does not prove the browser reached that server rather than a cached
response, and on macOS two processes can hold the same port on different address
families (IPv4 and IPv6) — observed while testing this. The
every-listener-must-be-ours check catches that case only if the stranger is
present when the check runs; one that arrives afterwards would not be seen.

#### 9. The E2E cleanup killed Docker Desktop

The fix in section 8 introduced a worse bug than the one it closed, and it is
worth recording as its own item because the shape of the mistake is the point.

Freeing port 5173 before starting was correct. Applying the same logic to port
8000 was not, because the script had no way to know what was on it. From
`main #13`:

    === port 8000 is already held by pid(s): 32061 - this is the leak, clearing it
    32061 32008 /Applications/Docker.app/Contents/MacOS/com.docker.backend services

It killed Docker Desktop. Two stages later the Docker stage found no daemon and
Deploy found no cluster: **the pipeline killed its own dependency**, and did so
while reporting that it was tidying up after itself. The same logic also killed
a developer's `npm run dev` server during ordinary local work.

The assumption was never earned. A port number is not a claim of ownership, and
"this is the leak" was a guess written as a statement. **Killing an unknown
process is worse than failing**, because a failure is legible at the moment it
happens and a dead daemon three stages later is not.

The rule now is ownership, not force: a process may be killed only if its
process group was recorded by an earlier run of this script, or its command line
is one this stage starts *and* its working directory is inside this repository.
Anything else is named, with its command line and working directory, and the
stage fails telling the operator to stop it or move the port. Both ports are
configurable (`BA_E2E_API_PORT`, `BA_E2E_WEB_PORT`).

**It was blocked immediately, and that is the fix working.** `main #15` failed
with the stage refusing port 8000 because Docker Desktop's proxy held it: the
docker-compose stack publishes the gateway on 8000 and the frontend on 5173, the
same two ports the stage wanted, and Docker restores those containers whenever
it starts. The stage is now given ports of its own in the `Jenkinsfile`
(`BA_E2E_API_PORT=8111`, `BA_E2E_WEB_PORT=5111`).

**Making the ports configurable took three changes, not one.** A port setting
that only reaches the servers is a trap, because everything downstream still
assumes the defaults:

- `VITE_API_BASE` is baked into the bundle at build time and defaults to
  `http://localhost:8000`. On this machine that is the compose gateway, so the
  test would have driven our frontend against a different backend entirely and
  reported a pass.
- `browser_flow.py` reads `BA_E2E_API` and `BA_E2E_APP`, both defaulting to the
  same two ports, so it would have tested the compose stack.
- `core/config.py` allows CORS from `:3000` and `:5173` and nothing else. On any
  other port the browser's `/policies` fetch is blocked, the policy dropdown
  never populates, and the test times out on a selector - which looks exactly
  like a broken frontend and is not one. This one was found by running it.

All three are set by `run_stage.sh` from the two port variables.

**Making the ports configurable also needed a third proof.** The stage proved
the server was its own and the bytes were this run's, but nothing proved the
bundle *pointed* at this run's API - and `BA_E2E_SKIP_BUILD` writes the stamp
without building, so both existing proofs pass over a `dist/` baked against
whatever port the last real build used. On this agent that is 8000, the compose
gateway: the stage would have driven our frontend against a different backend
and reported a pass, which is the exact failure the port work exists to stop.
The build now records its base in `frontend/dist/ba-build-base.txt` and a
skipped build must match it or the stage refuses.

**One fixed pair was not enough either.** The node has two executors and
multibranch runs main and develop together. At 13:59:44Z both wanted 8111/5111:
main #17 got them and passed, develop #21 found 5111 held by a process in the
`bill-audit_main` workspace and refused. Correct behaviour, red build, nothing
to do with the commit. The ports are now `8100 + EXECUTOR_NUMBER` and
`5100 + EXECUTOR_NUMBER`, because executor numbers are unique among builds
running at the same time, which is the property the collision needs. Verified on
develop #22, which took 8101/5101 - the non-zero offset is the evidence the
variable reached the `environment` block instead of collapsing to 8100.

**What is still not solved.** The stage needs two free ports and will refuse
rather than work around a clash. That is the intended trade - a refusal is cheap
to diagnose, a dead daemon three stages later is not - but on an agent where
something else takes the pair this executor was given, the same refusal happens.

Two builds have never yet been observed running the stage *simultaneously* under
the new scheme; what is proven is that the offset resolves per executor. The
remaining hole is an aborted build, whose post block can be skipped: main #16
was aborted at 19:18 and left no cleanup behind it. A leaked server on an
executor's pair will be named clearly rather than silently tested against, but
it is still a red build for an unrelated reason.

#### 10. Guardrail 3 cannot tell a table cell from an exclusion

Guardrail 3 rejects a limit of Rs 0 unless the clause it cites contains
exclusionary language. Two clauses in this index carry the same exclusionary
language, satisfy `EXCLUSION_RE` in exactly the same way, and have **opposite
correct answers**:

| | `star_health II.20` | `hdfc_ergo E.2.1` |
|---|---|---|
| what the zero read off it is | **correct** | **wrong** |
| "Not Covered"/"Not Available" in the body | 2 | 2 |
| `[table]` markers | **10** | **0** |

`II.20` grants shared accommodation and its benefit table says "Not Available"
against the two lowest sums insured. A zero read off that row is the policy
speaking, and rejecting it would throw away a correct answer.

`E.2.1` is not a clause at all. It is a row of a plan-comparison grid that the
splitter read straight across, and it reads in full:

    Not Covered
    800 per day 800 per day 1000 per day 800 per day
    2.2 choosing Shared max upto 4800 max upto 4800 Not Covered

**No test over what the text means can separate these two.** Both are table
cells. Both say the same words. `EXCLUSION_RE` matches
`not\s+(?:be\s+)?(?:payable|covered|available|…)` against each of them
identically, and any pattern narrow enough to reject `E.2.1` on its wording
rejects `II.20` on the same wording. `core/exclusion.py` already records the
trade in its own module docstring: requiring the exclusion to appear in prose
would catch one more bad verdict and would reject that correct one.

The only thing that separates them is **whether the extractor succeeded**.
`II.20` has ten `[table]` markers because its table was read structurally;
`E.2.1` has none because its table was flattened. A guardrail keyed on that is
not testing whether the policy excludes the expense. It is testing whether the
clause is intelligible, which is a data-quality signal wearing a guardrail's
clothes — and it would rot the moment extraction improves, because a repaired
`E.2.1` would carry markers and pass the very check written to stop it.

**What this costs today: two confident wrong zeros, B21 and B28.** Both are
ambulance lines, both cite `E.2.1`, and both tell the insured that an expense
the policy covers is not payable, with a real clause reference beside it. That
is 2 of 328 scored lines. The extent was measured before this was written —
`eval/table_corruption_survey.md` — and `E.2.1` is the only genuinely corrupt
clause in the index, so the count is small and is not expected to grow.

This is a limit of the approach, not a task waiting to be done. Guardrail 3 asks
whether the cited clause excludes *anything*; separating a cell from a rule
needs the exclusion tied to the specific expense being judged, which is the
general case, and the general case is where false rejections start costing
correct answers (see section 7). Fixing `E.2.1` at source removes these two
lines. It does not close the hole, because the next flattened table would land
in it the same way.

---

# 9. The debugging stories

Each has the same five parts: symptom, the hypothesis that was wrong, the
measurement that settled it, the fix, and the number it moved.

## 9.1 The phantom space in `star_health.pdf`

**Symptom.** The clause index carried `E xpenses related to the treatment of the
following listed Conditions`. Every BM25 term that crossed one of these breaks
was destroyed — a lexical search for "Expenses" could not match "E xpenses" —
and the embedding for the clause was computed over corrupted text.

**Wrong hypothesis.** That the two-column crop was slicing characters, or that
the font had letter-spacing (the splitter already carries `fix_letter_spacing`
for `O rgan` and `A YUSH`, so this looked like more of the same).

**The measurement that settled it.** Reading the glyph geometry off page 28
directly:

```
previous glyph  '\t'   x0=552.755  x1=555.692  top=299.974
phantom space   ' '    x0=552.755  x1=555.692  top=299.974
next glyph      'p'
extracted as:   '\t pre-existing'
```

The space has **identical `x0`, `x1` and `top`** to the character before it. It
is not a space between two glyphs; it is a space painted **on top of** one. That
is a positional fact, not a font fact, and it is what distinguishes this from
letter-spacing.

**The fix.** `core/splitter.without_phantom_spaces`, which drops a space whose
bounding box coincides with its neighbour's. **79 occurrences, across 26 clause
bodies and 6 titles.**

**The number it moved: 51.5% → 54.0%** line accuracy over 44 bills — recorded as
`v9-phantom-spaces`. Retrieval recall@3 over three angles moved 52.1% → 52.5%;
star_health's own single-angle recall@3 went **down**, 29.2% → 23.6%, while its
three-angle figure went **up**, 40.6% → 41.5%. Cleaner text ranks differently,
not uniformly better.

## 9.2 The E2E stage that never tested its own build

**Symptom.** `develop #17` failed: Selenium timed out on
`[data-testid='bill-text']`, an element the current bundle had.

**Wrong hypothesis.** That the frontend was broken, or that the preview server
needed longer to start. The instinct was to raise the timeout.

**The measurement that settled it.** The build log's own timestamps:

```
develop #17:  16:27:20  + curl -sf http://localhost:5173
              16:27:20  + break
```

**One second into the stage, before `npm ci` had finished.** Nothing this build
made could possibly have been listening. The readiness check asked whether
*something* answered, never whether it was ours — and the faster it passed, the
more certainly it was wrong. `npx` forks vite as a child, so `kill $!` killed the
wrapper and every build donated an orphan to the next.

Then the same defect was found **passing**: `main #11`'s own preview server died
with "Port 5173 is already in use", the failure was swallowed by the background
subshell, and four tests went green against a build nobody made. **Green and red
for the same wrong reason.**

**The fix.** `tests/e2e/run_stage.sh` with the three proofs — process group,
build stamp, baked API base — plus per-executor ports.

**The number it moved.** No accuracy number. What it moved is the meaning of
every previous E2E result: **no E2E run before 2026-09-04 is evidence of
anything, including the green ones.** A green E2E stage in an old build does not
mean the frontend worked; it means something was listening.

## 9.3 The `cache_put` race

**Symptom.** `FileNotFoundError` raised out of the disk cache during parallel
audits, taking the bill line down with it.

**Wrong hypothesis.** Uncertain — the repository does not record what was
suspected first.

**The measurement that settled it**, recorded in `core/cache.py`: a shared
`<name>.tmp` temp file **fails 153 times in 240 concurrent writes on one key.**
Two workers writing the same cache key both create `<name>.tmp`; one renames it
into place, the second then finds its own temp file gone.

**The fix.** One atomic write, `write_json`, in `core/cache.py`, with the temp
file carrying **the writer's identity** rather than a shared name. Put in a
shared module on purpose, so the second cache — `core/retrieve.py` caches
searches by query, `core/llm.py` caches answers by prompt hash — cannot
reintroduce the bug the first one had. `key_digest` is the single canonical
serialisation, pinned by `tests/test_llm_cache.py` so a change to it cannot pass
silently: every entry already on disk was addressed with it.

**The number it moved.** No accuracy number; it is a crash, not a wrong answer.
153/240 → 0.

## 9.4 `main #21` building images past skipped gates

**Symptom.** `main #21` built and tagged five images as `21`, and Deploy
attempted a rollout with them.

**Wrong hypothesis.** That the build was fine because it was not red.

**The measurement that settled it.** Reading what the build actually did: Eval
was skipped (no Ollama) and E2E was skipped (no Ollama, no npm). **Neither ran.**
The build went `UNSTABLE` rather than `FAILURE`; Docker read `currentBuild.result`
as "not failed", and built. **Those images came from code whose accuracy gate and
browser tests had never executed.**

**The fix.** The gate ledger: two `@Field` maps, `gatePassed()` called as each
gate's own last act, and Docker/Deploy/Prune reading those records **and nothing
else — never `currentBuild.result`**. Belt and braces: on `main` a missing
prerequisite also aborts the build outright.

**The number it moved.** None. The value is the class of build it makes
impossible: `"Not failed" is not "passed". A gate that could not run has proved
nothing.`

## 9.5 The coverage guard that could not run in CI

**Symptom.** `develop #41` reported **9 errors — every test in
`test_index_coverage`, all three policies, all three methods.** The identical
suite passed 477 OK locally.

**Wrong hypothesis.** A pinned count gone stale in the merge — the shape of the
last three failures in that file.

**The measurement that settled it.** The archived junit XML rather than the test
source:

```
FileNotFoundError: [Errno 2] No such file or directory:
  '/Users/.../workspace/bill-audit_develop/data/policies/hdfc_ergo.pdf'
  tests/test_index_coverage.py line 66, in _index
    clauses = split_pdf(settings.policies_dir / PDFS[policy], policy)
```

**Errors, not failures, and 9 of 9** — the module could not run at all. The
guard re-split the PDFs on every run, and `.gitignore` carries
`data/policies/*.pdf`. It could only ever work on the author's machine.

**The fix.** Read `data/clauses.json` — a committed checkpoint present in every
checkout — and pin each page as a 30-character squashed probe in the fixture. The
probe sets came out identical to the pinned page lists, 48 / 27 / 42, so the
conversion was lossless. Proved both directions in a scratch tree with no
`data/policies/` at all: 4 tests OK, and after deleting `E.2` from that copy,
`page(s) [49, 50, 51] no longer appear anywhere in the index`.

**The number it moved.** 19 seconds → 0.013 seconds, and 9 errors → 0. The guard
was **not** made to skip: a guard that does not run in CI is not a guard, and
this one exists precisely because 474 tests passed while two pages left the
index.

## 9.6 The `E.2`/`E.3` split, made and reversed

**Symptom.** `hdfc_ergo E.2` was 12,414 characters and broke the
`assertLess(len(clause.text), 12_000)` cap in `tests/test_ingest.py`.

**Wrong hypothesis.** That `E.2` was under-split and should be cut at the
boundary between its rendered table rows and the prose beneath. Done in
**BA-240**: `E.2` 9,748 + `E.3` 2,665.

**The measurement that settled it.** Nine queries run against both halves:

- the two halves came back together **twice** out of nine
- `QUERY_ANGLES["other"]` angle 1 returned the grid at **rank 2** with the
  legend **nowhere in the top 25** — so no `rerank_top_n` widening recovers it
- `refs` is empty on both, so `with_references` has no citation to follow
- the legend names its target **positionally** — "Key to read *above table*" —
  which nothing in the index can resolve once they are separate records

**The fix — reversing it, in BA-242.** A judge handed the grid without its key
reads "Not Covered" with no definition of what that means in that grid, which is
exactly how B21 and B28 produced a confident Rs 0 on lines the key pays in full.

The cap was then reworked rather than raised, into two tests: **prose** under
12,000 (`E.2` is 2,666) and **total** under 16,000 (`E.2` is 12,414). Capping
prose alone would leave a runaway table unbounded; a percentage-of-table
exemption was considered and rejected because a ratio puts no bound on the
absolute prose payload — 40,000 characters of table plus 13,000 of prose is 75%
table and would be waved through.

**The number it moved.** No eval row; the split never reached a recorded run. It
cost one character in the coverage floor (the newline between the two halves,
`9748 + 2665 = 12413` against `12414`) which was the signal that the change was
structural rather than free.

## 9.7 The top-5 retrieval experiment, reverted

**Symptom.** Not a bug — a hypothesis. recall@3 was 34.5%, meaning **the judge
never saw the right clause on two-thirds of lines.** The obvious move is to show
it more clauses.

**Wrong hypothesis.** That accuracy was limited by what reached the judge, so
raising `rerank_top_n` from 3 to 5 would raise accuracy.

**The measurement that settled it.** The full 44-bill run, recorded as
`v10-top5`:

| | v9 (top 3) | v10 (top 5) |
|---|---|---|
| recall at the cut | 34.5% | **44.4%** |
| line accuracy | **54.0%** | **47.3%** |
| false answers | 5 | **12** |
| abstention recall | 83.3% | 60.0% |

**Recall went up and accuracy went down.** More right clauses in front of the
judge did not make the judge more right — it gave it more to be wrong about, and
**more than doubled the false answers**, which is the worst failure mode short of
a fabricated citation.

**The fix.** Reverted. `rerank_top_n` stays at 3, and the row was kept in
`eval/results.md` rather than deleted.

**The number it moved: 54.0% → 47.3%, and back.** Its value is negative
knowledge: the bottleneck is not what the judge is shown.

## 9.8 The v6 drop — merged table cells

**Symptom.** Line accuracy fell from `v5-full`'s 59.5% to 50.0%.

**Wrong hypotheses, both ruled out by measurement.** (1) `core/room_limit.py` —
ruled out; it resolves all nine star_health sums insured correctly, and is now
pinned by `tests/test_room_limit_golden.py`. (2) the retrieval device (mps vs
cpu) — ruled out; `v6-cpu` reproduces `v6` on every accuracy metric, which is
why both rows exist.

**The measurement that settled it.** The table extractor was reading a
horizontally merged cell as belonging only to its first column, and the
forward-fill then carried column headings down into data rows. Fixing it removed
corrupted text from **11 of 402 clauses, 5 of them star_health**. Cleaner text
means a different embedding, so those clauses rank differently, and the judge —
given a different top three — answered differently on **45 star_health lines,
all of which went from answered to abstained.**

**The conclusion.** **Part of the old 59.5% was luck on corrupted data.** 50.0%
on a correct index is the honest figure. The number went down and the system got
better.

## 9.9 The Deploy stage that never deployed

**Symptom.** `kubectl apply -f k8s/` green every time, deploying nothing.

**The measurement that settled it.** Pod creation timestamps: the pods running
on 2026-09-05 were created `2026-09-03T15:23:44Z`. **Build 22 had finished an
hour earlier and had never reached the cluster.**

**Three causes, all present at once.** Images stayed in Docker Desktop's daemon
(minikube runs its own); every manifest pinned `:latest` so the Deployment spec
was byte-identical build to build and `kubectl apply` started no rollout; and
`imagePullPolicy: IfNotPresent` meant even a restarted pod kept its old image.

**The fix.** `k8s/deploy.sh` — load, render the BUILD_NUMBER tag, apply, wait,
then read the image back off every pod.

**The number it moved.** None. Two days of green Deploy stages meant nothing.

## 9.10 The E2E cleanup that killed Docker Desktop

**Symptom.** From `main #13`:

```
=== port 8000 is already held by pid(s): 32061 - this is the leak, clearing it
32061 32008 /Applications/Docker.app/Contents/MacOS/com.docker.backend services
```

**What happened.** The fix for 9.2 introduced a worse bug than the one it closed.
Freeing port 5173 before starting was correct. Applying the same logic to port
8000 was not, because the script had no way to know what was on it — and what
was on it was Docker Desktop.

**The fix.** The stage now names any process it did not start, with its command
line and working directory, and **fails telling the operator** rather than
killing it. Plus its own ports, `8100`/`5100` + executor number.

**Why this one is recorded as its own limitation** (section 9 of
`KNOWN_LIMITATIONS.md`): the shape of the mistake is the point — a cleanup that
assumes everything it finds is its own.

## 9.11 The answer-key audit that found nothing

**Symptom.** A recorded belief that 37 of 93 citations in the answer key were
wrong.

**The measurement.** `eval/repair_answer_key.py` searches every clause for the
text each derivation quotes. **0 of 261 cited lines moved.** The "37 of 93"
figure was stale — decision D-12 had already fixed them.

**The outcome.** `v8-key-audit` records **identical numbers to v7** — 51.5%,
44.4%, 3 false answers. `eval/derive_key.py --write` is now **refused**, because
it would revert 87 recorded decisions, and the divergence is pinned by
`tests/test_derive_key_divergence.py`. 72 rows in 5 questions remain for a human
and a PDF, listed in `eval/answer_key_todo.md`.

**The number it moved.** Zero, exactly. A recorded row whose value is that it
changed nothing.

---

## 9.12 The thread fix that was slower than the defect

**The symptom.** One 10-line bill took 34 minutes through the cluster on Groq,
with zero rate-limit waits and zero fallbacks. Profiling put ~99% of a search in
the cross-encoder and found the cause: `retrieval-service` ran under
`limits: { cpu: "1" }` on a ten-core node, and torch sizes its thread pool from
`os.cpu_count()`, which reports the machine and knows nothing about a cgroup
quota. Ten threads inside one core's budget: **8,109 of 8,163 periods throttled,
5,872s of throttled time against 815s of CPU actually used.**

**The fix that made it worse.** The obvious repair is to call
`torch.set_num_threads()` before the reranker loads. Measured at `--cpus=1`,
five searches:

| | rerank s/search |
|---|---|
| 10 threads, untouched | 165.95 |
| `set_num_threads(2)` after torch was imported | **191.23** |
| `OMP_NUM_THREADS=2` set before the import | 117.81 |

**The middle row is the trap.** torch reports two threads and dispatches two
work items, but the OpenMP pool underneath was already built with ten and torch
does not own it — half the parallelism, all of the thrash. Nothing in
`torch.get_num_threads()` reveals this; it returns 2 in both cases. Only the
clock separates them.

**What that cost in evidence.** The first proof of "does torch read
`OMP_NUM_THREADS` at import time?" set the variable after `import torch`, read
`get_num_threads()`, saw 2, and concluded the placement did not matter. The
number was right and the conclusion was wrong: reporting is not the same as the
pool being resized.

**The outcome.** `core/cpu.py` splits into `set_thread_env()`, which publishes
the count into `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `OPENBLAS_NUM_THREADS`
and imports nothing heavy, called at service start-up before anything can import
torch; and `apply_torch_threads()`, which does that plus `set_num_threads()` as
a backstop at model load for the CLI and the eval, which have no start-up hook.
Same harness both sides: **146.25s → 103.49s per search, 1.41x**, throttled time
5,368s → 534s. The work is provably unchanged — the cross-encoder scored the
same `[48, 72, 66, 73, 70]` documents in every run.

**A second measurement fault, caught the same way.** One "before" run silently
measured the "after" configuration: a shell variable holding `-e
BA_TORCH_THREADS=10` did not word-split in zsh, so the flag never reached
docker. The start-up log line is what exposed it — it said `threads=2` in a run
labelled 10.

---

# 10. The stack

Versions are the **resolved** versions from `uv.lock` and `package.json`, not
the `>=` floors in `pyproject.toml`.

## Languages and runtimes

| | version | where |
|---|---|---|
| Python | **3.14.6** (`requires-python = ">=3.14"`) | everything under `core/`, `api/`, `services/`, `eval/`, `tests/`, `ci/` |
| TypeScript | **5.6.3** | `frontend/` |
| Node | **22** (alpine, build stage only) | `frontend/Dockerfile` |
| Groovy | uncertain (Jenkins-provided) | `Jenkinsfile` |
| Bash / sh | POSIX sh | `k8s/deploy.sh`, `tests/e2e/run_stage.sh`, `.githooks/*` |

## Models

| role | model | served by |
|---|---|---|
| judge, classify — eval and CLI | **`qwen3:8b`** | Ollama, `http://localhost:11434` |
| judge, classify — API path, and every service in Kubernetes | **`openai/gpt-oss-120b`** | Groq |
| judge, classify — fallback in Kubernetes | **`qwen3:8b`** | Ollama, `http://ollama:11434` |
| embeddings | **`BAAI/bge-base-en-v1.5`** | sentence-transformers, in-process |
| cross-encoder rerank | **`BAAI/bge-reranker-base`** | sentence-transformers, in-process |

`num_ctx = 8192` on every Ollama call. The default is 2048 and truncates
retrieved clauses **silently** — no error, just confident nonsense.
`temperature = 0.0`. `keep_alive = "30m"`. `llm_num_predict = 2048`, a hard cap
because without it a looping model streams for ever. `llm_timeout_s = 180`.

Groq rate limits, from `core/config.py`: 8,000 tokens/minute, 30 requests/minute,
1,000 requests/day, 4 retries, backoff base 2.0s, timeout 60s, cooldown 120s.

## Python libraries

| package | version |
|---|---|
| fastapi | 0.141.1 |
| starlette | 1.6.0 |
| uvicorn | 0.52.4 |
| pydantic | 2.13.5 |
| pydantic-settings | 2.15.0 |
| httpx | 0.28.1 |
| python-multipart | 0.0.32 |
| langgraph | 1.2.11 |
| langgraph-checkpoint | 4.2.0 |
| langgraph-prebuilt | 1.1.0 |
| langchain | 1.3.18 |
| langchain-core | 1.6.1 |
| langchain-chroma | 1.1.0 |
| langchain-classic | 1.0.8 |
| langchain-community | 0.4.2 |
| langchain-groq | 1.1.3 |
| langchain-ollama | 1.1.0 |
| langchain-text-splitters | 1.1.2 (present as a transitive dep; **not used on policy documents**) |
| chromadb | 1.5.9 |
| rank-bm25 | 0.2.2 |
| sentence-transformers | 6.0.1 |
| transformers | 5.16.1 |
| tokenizers | 0.23.1 |
| huggingface-hub | 1.29.0 |
| torch | **2.14.0+cpu** |
| numpy | 2.5.2 |
| scipy | 1.18.1 |
| scikit-learn | 1.9.0 |
| onnxruntime | 1.29.0 |
| pdfplumber | 0.11.10 |
| pdfminer-six | 20260107 |
| pypdfium2 | 5.13.0 |
| pillow | 12.3.0 |
| ollama | 0.6.2 |
| groq | 0.37.1 |

## Tooling

| tool | version | role |
|---|---|---|
| uv | **0.12.0** | dependency resolution and running |
| ruff | 0.16.5 | linter **and** formatter |
| PyBuilder | 0.13.21 | how Jenkins runs the tests |
| flake8 | 7.3.0 | runs in the build only — decision **D-09** |
| coverage | 7.16.0 | gate at 75%, measured at 79% — decision **D-11** |
| selenium | 4.48.0 | E2E |
| unittest | stdlib | the test framework; **not pytest** |

ruff config: `line-length = 100`, `target-version = "py314"`, selecting
`E, F, I, UP, B, C4, SIM, PTH, RUF`, ignoring `E501` (the formatter owns line
length), `RUF012` and `B008`.

## Frontend

| package | version |
|---|---|
| react | ^18.3.1 |
| react-dom | ^18.3.1 |
| react-router-dom | ^6.30.6 |
| @tanstack/react-query | ^5.59.0 |
| vite | ^5.4.10 |
| @vitejs/plugin-react | ^4.3.3 |
| typescript | ^5.6.3 |

Scripts: `dev`, `build` (`tsc -b && vite build`), `build:pages`
(`vite build --mode pages`), `preview`, `typecheck`.

## Infrastructure

| | version |
|---|---|
| Docker base, Python services | `python:3.14-slim` |
| Docker base, frontend build | `node:22-alpine` |
| Docker base, frontend runtime | `nginx:1.27-alpine` |
| Ollama image | `ollama/ollama:latest` |
| Jenkins | 2.541.1 |
| Kubernetes | minikube, version uncertain |
| git | 2.50.1 (Apple Git-155), as reported by the Jenkins agent |

## Explicitly banned

Recorded in `CLAUDE.md` as "Do not add": SQLite, Redis, Celery, Ragas,
Langfuse, any paid API, authentication, a database, and **LangChain text
splitters on policy documents**.

---

# 11. Repository map

## Top-level files

| path | what it is |
|---|---|
| `CLAUDE.md` | operating rules for working in the repository; the current-state block |
| `ENGINEERING.md` | the engineering record — why the splitter, retrieval, guardrails and pipeline are as they are |
| `KNOWN_LIMITATIONS.md` | ten numbered limitations, reproduced in section 8 above |
| `DECISIONS.md` | D-01 to D-15, each a decision with its reasoning |
| `PHASES.md` | the phase plan, 672 lines |
| `BLOCKED.md` | what is unverified, as opposed to unbuilt — B-01, B-02 |
| `README.md` | the public-facing description and headline results |
| `JENKINS_SETUP.md` | how the Jenkins job is configured |
| `GIT_FIX.md` | uncertain — not read for this inventory |
| `PROJECT_FACTS.md` | this file |
| `Jenkinsfile` | the multibranch pipeline |
| `pyproject.toml` | project metadata, dependencies, extras, ruff config |
| `uv.lock` | the resolved lockfile |
| `requirements.txt` | generated export, **never hand-edited** |
| `requirements-{audit,gateway,ingestion,retrieval}.txt` | per-image exports |
| `build.py` | PyBuilder build descriptor |
| `docker-compose.yml` | the six-container local stack |
| `docker-compose.override.yml` | local overrides, gitignored |
| `eval_full.log`, `eval_full2.log` | eval run logs, gitignored by `*.log` |

## Directories

| path | what it is |
|---|---|
| `core/` | the library. Imports no web framework |
| `api/` | the FastAPI monolith — `main.py`, `jobs.py`, `shared.py` |
| `services/` | the same core split into four containers, plus `common.py` |
| `frontend/` | React + TypeScript + Vite SPA |
| `eval/` | the harness: 44 bills, the answer key, `evaluate.py`, `recall.py`, `results.md` |
| `tests/` | 492 PyUnit tests, plus `e2e/` and `fixtures/` |
| `k8s/` | eleven manifests plus `deploy.sh` |
| `ci/` | `prune_images.py` |
| `data/` | `clauses.json`, `non_payable.json` committed; `db/`, `llm_cache/`, `policies/*.pdf`, `traces/` gitignored |
| `docs/` | four screenshots: `audit-1440.png`, `site-landing-1440.png`, `jenkins-main-green.png`, `jenkins-prune-blocked.png` |
| `src/bill_auditor/` | the packaged console script. `core/` and `api/` live outside `src/` and are import-path-only |
| `target/` | PyBuilder output, gitignored |
| `.githooks/` | `commit-msg` (format, 72-char subject, `[BA-XX]` ticket) and `pre-commit` (secrets, then the Lint stage's two commands on the whole tree) |

## `core/` module by module

| module | role |
|---|---|
| `config.py` | every setting, `BA_` env prefix, single source of truth |
| `llm.py` | Ollama and Groq calls, sha256 disk cache |
| `backends.py` | backend selection, rate limiting, fallback |
| `cache.py` | what the two disk caches share: `key_digest` and the atomic `write_json` |
| `logging_conf.py` | logging plus the JSONL `TraceWriter` |
| `models.py` | the Pydantic contracts, including `JudgeOutput` and `Limit` |
| `masking.py` | PII stripped before any prompt |
| `bill.py` | bill text → validated `BillLine`s |
| `money.py` | **all arithmetic** |
| `assumptions.py` | differential billing, stated rather than hidden |
| `splitter.py` | PDF → clauses. The largest module |
| `ingest.py` | clause labelling, the Chroma collection, the BM25 index |
| `cpu.py` | the cgroup CPU quota, and the torch thread count derived from it |
| `embeddings.py` | the embedding model wrapper |
| `retrieve.py` | hybrid search, sentence windows, rerank, the query cache |
| `audit.py` | the naive **v0** path |
| `agent.py` | the **v2** LangGraph loop and two of the guardrails |
| `room_limit.py` | the **v4** deterministic room-rent lookup |
| `waiting.py` | the **v5** waiting periods |
| `second_pass.py` | the **v3** proportionate deduction |
| `exclusion.py` | `states_an_exclusion` — what guardrail 3b decides from |

## `frontend/src`

| path | role |
|---|---|
| `routes/Landing.tsx`, `routes/AuditPage.tsx` | the two screens |
| `components/BillForm.tsx` | the four inputs |
| `components/ReportView.tsx` | the line-by-line table |
| `components/LineRow.tsx` | one line, its clause, its arithmetic |
| `components/AssumptionsPanel.tsx` | the assumptions lifted out of the trace |
| `components/CompareView.tsx` | policy comparison |
| `components/RunningPanel.tsx`, `Skeletons.tsx` | the 30–60s wait |
| `components/SubmittedSummary.tsx`, `ErrorBoundary.tsx`, `icons.tsx` | — |
| `hooks/useAuditJob.ts` | owns the polling |
| `hooks/useReveal.ts` | IntersectionObserver reveal |
| `lib/api.ts` | the one configurable base URL — decision **D-05** |
| `lib/arithmetic.ts` | derives the shown arithmetic, then **reconciles against the server figure and discards if it does not match** |
| `lib/staticDemo.ts` | the GitHub Pages no-backend path |
| `lib/csv.ts`, `lib/billStats.ts`, `lib/exampleBill.ts` | — |
| `data/exampleReport.json` | a real v11 B01 checkpoint |

## `eval/`

| path | role |
|---|---|
| `bills/` | 44 bill fixtures, plus `text/` and `INDEX.md` |
| `answer_key.json` | the hand-written key |
| `derive_key.py` | builds a key from the PDFs alone. Imports no retriever, judge or audit code, so a pipeline bug cannot score itself as a success. `--write` is refused |
| `evaluate.py` | the scorer. `--agent`, `--second-pass`, `--quick`, `--threshold`, `--version`, `--write` |
| `recall.py` | the retrieval ceiling at three depths |
| `results.md` | **the project's headline result**, 1,030 lines |
| `recall_before.md`, `recall_after.md` | the phantom-space fix, measured |
| `checkpoint.py` | the code-fingerprint keyed run cache |
| `repair_answer_key.py` | the key audit that found 0 of 261 |
| `make_text_bills.py` | writes each bill as pasteable text and cross-checks the two halves of every fixture |
| `export_example_report.py` | v11 B01 → `frontend/src/data/exampleReport.json` |
| `table_corruption_survey.py`, `.md` | the flattened-table detector and its negative result |
| `answer_key_todo.md` | 72 rows in 5 questions still needing a human and a PDF |
| `where_time_goes.py`, `audit_profile.py` | latency profiling |

---

# 12. History

**No git command was run to write this section.** Every claim below comes from a
file in the repository; where the repository does not record something, it says
**uncertain**.

## Commit count

**Uncertain.** The commit count cannot be established from the repository's own
files, and no git command was run.

## Ticket range

Every commit carries a `[BA-XX]` ticket at the end of the subject, enforced by
`.githooks/commit-msg`. Numbering is **continuous across the whole history** and
is not restarted per branch. From decision **D-01**:

> The tickets were dropped once, on the grounds that there is no issue tracker,
> and then reinstated: `PHASES.md` Part 4 and the Definition of Done both
> require them, and the numbering is a usable sequence even without a tracker
> behind it. `GIT_FIX.md` is the rewrite that put them back across the whole
> history.

**The highest ticket referenced anywhere in the repository is `BA-242`**
(`ENGINEERING.md`, the reversal of the E.2/E.3 split). `BA-999` also appears but
is an illustrative example in `DECISIONS.md`, not a real ticket. So the range in
use is approximately **BA-01 to BA-242**.

**Tickets are not commits.** Some tickets span several commits and some commits
were amended, so the ticket count is an upper bound on nothing in particular. It
is a sequence, not a census.

**How the enforcement failed once, which is why it is worth recording.** The
tickets went missing from an entire build without anything failing, for two
reasons at once: `core.hooksPath` was never set, so **no hook ran at all**; and
the hook had no ticket check in it. Both are fixed, and `tests/test_hooks.py`
runs the real hook against a message with no ticket and asserts it is rejected.

## How branches were used

GitFlow, documented in `CLAUDE.md`:

```
main  (tagged releases only)  <-  release/vX  <-  develop  <-  feature/short-name
```

- **`main`** — tagged releases. Runs the full pipeline including Docker, Deploy
  and Prune.
- **`develop`** — the integration branch. Runs Build, Quality, Eval and E2E.
- **`feature/<short-name>`** — one per piece of work. Runs Build and Quality only.
- **`release/vX`** — present in the model; `release/v1.0.0` exists as a branch.

Commits are **Conventional Commits**: `feat(agent): add retry loop with query
rewriting`. The `commit-msg` hook enforces the format **and a 72-character
subject limit**. The `pre-commit` hook checks for secrets first — any `.env*`
path except `.env.example` and `.env.pages`, plus a content scan for a Groq key
pattern — and then runs **the Lint stage's two commands verbatim on the whole
tree**: `uv run ruff check .` and `uv run ruff format --check .`.

It used to filter to staged `.py` files, and that let a failure through in
BA-245 (BA-246 fixed it). Ruff formats Python inside markdown fenced blocks as
well as in `.py` files, and this document quotes real source, so a hand-wrapped
quote is a formatting error in a file the filter never opened. The commit passed
the hook — `ruff check on 1 staged file(s)` — and `develop #45` failed Lint in
812ms. **What the hook still misses:** it checks the working tree, and CI checks
the commit, so a partial commit can pass one and fail the other. Simulating CI
exactly would mean stashing unstaged work inside a hook, which can lose it.

**One rule with a scar on it:** *always branch from `develop`.* Running
`git checkout -b feature/next` while still standing on the previous feature
branch stacks them, and `develop` then holds none of the work. This has already
happened once in this repository.

**Annotated tags mark eval milestones**, per `CLAUDE.md`: `v0` naive baseline,
`v1` hybrid retrieval, `v2` agent loop, `v3` second pass, `v4` all 8 guardrails,
`v1.0.0` submission. Note that `v4`'s description — "all 8 guardrails" — does not
match the built system: **three guardrails exist**, and `core/guardrails.py` is
not built.

## Roughly how long the project took

**The recorded evaluation history spans 2026-09-01 to 2026-09-06** — six days,
from the `v0` row to the `v12-ambulance-override` row in `eval/results.md`, with
a recorded row on every one of those dates.

| date | what `eval/results.md` records |
|---|---|
| 2026-09-01 | v0, v4, v5, v5-full |
| 2026-09-02 | the 10+10 rerank experiment, v6, v6-cpu, v7 |
| 2026-09-03 | ci-baseline-v7-quick |
| 2026-09-04 | v8-key-audit, v9-phantom-spaces, v10-top5, v11-zero-limit-guardrail |
| 2026-09-05 | (no eval row; the Deploy stage work) |
| 2026-09-06 | v12-ambulance-override |

**That is the span of the *recorded evaluation*, not necessarily of the
project.** Work that produced no eval row leaves no dated trace in these files —
the phases before the first eval, the frontend, the containers, the Jenkins
setup. **The total project duration is uncertain** and cannot be established
from the repository without git history.

The other dates that appear throughout `eval/bills/` — 2019 through 2026 — are
**policy start dates and admission dates inside the bill fixtures**, not project
dates. `eval/bills/text/INDEX.md` line for B28, as an example:

```
| B28 | hdfc_ergo | 2,500,000 | 2019-07-14 | 2026-01-05 | Rs 10,000/day | room_rent_over | 818,000 |
```

## What the phases were

`PHASES.md` is 672 lines and holds the plan. `CLAUDE.md` records that **every
phase in it is built, including Jenkins**, and that what remains is *unverified*
rather than unbuilt, tracked in `BLOCKED.md`. Phase numbers referenced elsewhere
in the codebase:

| phase | what it delivered |
|---|---|
| 3 | retrieval, and the two measurements about query specificity |
| 6 | the agent loop |
| 7 | the second pass and the guardrails |
| 8 | `api/` |
| 9 | `frontend/` |
| 10 | `services/`, the four-container split |
| 11 | Docker, `k8s/`, `build.py`, `Jenkinsfile` |

---

# Appendix: facts that contradict each other

Recorded because a portfolio page built from the wrong side of one of these
would be wrong.

| claim | where | status |
|---|---|---|
| "402 clauses in `data/clauses.json` (star_health 153, hdfc_ergo 144, niva_bupa 105)" | `CLAUDE.md` line 68 | **stale.** Measured today: **399** (152 / 143 / 104) |
| "474 tests" and "474 PyUnit tests, all passing" | `CLAUDE.md` lines 12 and 79 | **stale.** Measured today: **492**. Jenkins `main #28` recorded 478, before BA-247 added 14 |
| "all 402 clauses were labelled `other`" | `CLAUDE.md` line 100 | correct **as history** — it describes the B-02 defect at the time, when there were 402 |
| "`v4` all 8 guardrails" | `CLAUDE.md` line 155, the tag list | **wrong.** Three guardrails exist; `core/guardrails.py` is not built |
| "`second_pass.py` and `guardrails.py` are **planned for Phase 7 and do not exist**" | `ENGINEERING.md` line 400 | **half stale.** `second_pass.py` exists and is built; `guardrails.py` genuinely does not |
| "`frontend/`, `k8s/` — **empty directories**" | `ENGINEERING.md` line 402 | **stale.** Both are built and deployed |
| "`tests/` — PyUnit, 122 tests. `tests/e2e/` (Selenium 4) is planned and **does not exist yet**" | `ENGINEERING.md` line 404 | **stale.** 478 tests; `tests/e2e/` exists and runs in CI |
| "a candidate-set ceiling of 99.2% over the three query angles" | `ENGINEERING.md` line 20 | **not reproducible** from `eval/recall_after.md`, which reports 72.4% in the candidate set. Provenance **uncertain** |

Two things that look like contradictions and are not:

- **`PHASES.md` lines 178–179 give v2 as 51.2% and v3 as 54.9%.** The file marks
  both **"not reproducible"** in the row itself and explains why in the note
  above the table: `eval/results.md` holds no row for either, so neither can be
  checked against a code fingerprint. They are left as a record of what was
  believed at the time. That is disclosure, not a stale number.
- **`CLAUDE.md` has already been corrected on the eval threshold.** It says
  `--threshold 0.52` on the 10-bill subset, which matches the `Jenkinsfile`. An
  earlier gate of 0.65 is referenced only as history.

The pattern in that table is worth noting on its own: **the stale numbers are
all in the two prose documents, and none of them are in `eval/results.md`.** The
results file is append-only and every row records what produced it. That is why
`CLAUDE.md` names it the only authoritative source for an accuracy number.
