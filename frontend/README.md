# Frontend

React + TypeScript + Vite, with React Query owning the polling.

The whole system, this front end included, comes up on compose:

```bash
cd .. && cp .env.example .env    # add your BA_GROQ_API_KEY
docker compose up -d             # UI on http://localhost:5173, gateway on :8000
```

For front-end work, run vite against that gateway instead — the dev server
reloads, the nginx image does not:

```bash
npm install
npm run dev        # http://localhost:5173, needs :8000 answering
```

`docker compose up -d gateway` is enough to serve it, or `uv run uvicorn
api.main:app --reload` for the monolith. Set `VITE_API_BASE` to point somewhere
else (see `.env.example`).

## The GitHub Pages build

The front end is published on its own at
<https://pavansai2608.github.io/bill-auditor/>, separately from Jenkins, by
`.github/workflows/pages.yml` on every push to `main`.

```bash
npm run build:pages          # reads .env.pages
```

Three things differ from `npm run build`, all of them consequences of Pages
serving files from a **subpath** with no server in front of them:

| | why |
|---|---|
| `base` is `/bill-auditor/` | an asset written against `/` resolves to the domain root and 404s in production while working perfectly on localhost |
| `index.html` is copied to `404.html` | Pages has no rewrite rule, so a hard refresh on `/bill-auditor/audit` asks for a file that is not there |
| the audit form is disabled | there is no API to post to, and a form that posts into nothing is worse than one that says so |

The router reads `import.meta.env.BASE_URL` rather than repeating the literal,
so the basename and the asset paths cannot drift apart.

**The site cannot run an audit, and says so.** The audit is a retrieval
pipeline over a 399-clause index, judged by a model; none of that is on a CDN.
The note on the form sums its clause count from `STATIC_POLICIES` in
`src/lib/staticDemo.ts`, which is the one place the front end states one.

What the site can show is a report the system really produced -
`src/data/exampleReport.json`, exported from an eval checkpoint by
`eval/export_example_report.py` and pinned to the clause index by
`tests/test_example_report.py`. Nothing on that screen is invented.

To check a Pages build the way Pages will serve it:

```bash
uv run python tests/e2e/pages_static_check.py
```

## Where things are

- `src/hooks/useAuditJob.ts` — starts a job and polls it. All the polling rules
  live here: every 2 seconds, stop on `done` or `failed`, give up after 5
  minutes.
- `src/context/AuditContext.tsx` — the job id and the form values, shared
  without threading props through every component.
- `src/components/ErrorBoundary.tsx` — catches a render crash so the whole page
  does not go white.
- `src/App.tsx` — loads the report screen with `React.lazy`, so the table and
  CSV code are not in the first bundle.
