# Frontend

React + TypeScript + Vite, with React Query owning the polling.

```bash
npm install
npm run dev        # http://localhost:5173
```

The API must be running on http://localhost:8000:

```bash
cd .. && uv run uvicorn api.main:app --reload
```

Set `VITE_API_BASE` to point somewhere else (see `.env.example`).

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
