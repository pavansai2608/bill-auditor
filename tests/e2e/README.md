# End-to-end test

One test, driving a real browser against the real API and the real model.

## Start both halves first

Two terminals, from the repository root:

```bash
# terminal 1 - the API
uv run uvicorn api.main:app --port 8000

# terminal 2 - the frontend
cd frontend && npm install && npm run dev
```

Ollama must be running with `qwen3:8b` pulled, and the clause index must exist
(`uv run python -m core.ingest` once).

## Run it

```bash
uv run python -m unittest tests.e2e.browser_flow
```

Expect `Ran 2 tests ... OK`, in about a minute the first time and a few seconds
afterwards, because every model call is cached to disk.

## If it skips

The test checks `http://localhost:8000/health` and `http://localhost:5173`
before it starts, and skips with the command to start whichever one is missing.
That is deliberate: a developer running the whole suite should not get a
failure for not having a browser stack up.

To turn those skips into failures - which is what Jenkins does, because there
the services really are started first:

```bash
BA_E2E_STRICT=1 uv run python -m unittest tests.e2e.browser_flow
```

## Settings

| Variable | Default | What it does |
|---|---|---|
| `BA_E2E_API` | `http://localhost:8000` | where the API is |
| `BA_E2E_APP` | `http://localhost:5173` | where the frontend is |
| `BA_E2E_HEADLESS` | `1` | set to `0` to watch it drive the browser |
| `BA_E2E_STRICT` | unset | `1` makes a missing service a failure, not a skip |

## Why the expected figure is 25,000

The bill is two lines and neither needs the model to judge it:

- `Room Rent (Single A/C) 8,000 x 5 days` — star_health prices the room limit
  by sum insured, and at 3,00,000 clause II.1 gives 5,000 a day. Five days is
  25,000, which is less than the 40,000 charged.
- `Surgical Gloves` — item 1 on the IRDAI non-payable list, so nil.

Only the bill parsing calls the model. If this figure changes, either the room
table stopped being read correctly or the non-payable fast path stopped firing;
both are more serious than a failing browser test.
