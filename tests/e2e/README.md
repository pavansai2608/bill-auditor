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

## The other check in here: the GitHub Pages build

`pages_static_check.py` is a different test of a different thing. `browser_flow`
proves the whole system works; this proves the build that has **no backend at
all** works, served the way GitHub Pages serves it.

```bash
uv run python tests/e2e/pages_static_check.py             # builds first
uv run python tests/e2e/pages_static_check.py --no-build  # reuse frontend/dist
uv run python tests/e2e/pages_static_check.py --headed    # watch it
```

It needs no API, no model and no clause index — only Chrome. `pages_server.py`
serves `frontend/dist` under `/bill-auditor/` and answers an unknown path with
`404.html` **and a 404 status**, which is what Pages does and what the SPA
fallback has to survive.

It exists because every way a Vite app breaks on Pages breaks *only* on Pages,
and all of them look perfect locally:

- an asset written against `/` resolves fine at a domain root and 404s under a
  project subpath;
- a router with no basename matches every route locally and none in production;
- a deep link works on any server with a rewrite rule and dies on Pages, which
  has none;
- and `http://localhost:8000` inlined into a public bundle sends every
  visitor's browser at a server on their own machine.

So the assertions are made against what the browser rendered and against the
requests the page actually issued — read back off `performance.getEntriesByType`
— never against the source that was supposed to produce them. Finding the
localhost string absent from `dist/` is not the same claim as finding that the
page contacted nobody but the CDN and Google Fonts; this checks the second.

Two details it has to work around, both of which otherwise read as missing data
rather than as timing:

- `styles.css` sets `scroll-behavior: smooth`, so `scrollIntoView` is
  asynchronous and a click lands where the element used to be. It scrolls with
  `behavior: 'instant'`.
- the report arrives with `animation-fill-mode: both`, so its first frames are
  at `opacity: 0` — and Selenium reads an opacity-0 element as neither shown
  nor having any text. It waits for the animation to settle before reading a
  figure.
