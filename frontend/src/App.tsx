import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import Landing from "./routes/Landing";

// The landing page is the front door and ships in the entry bundle. Everything
// the audit needs - the form, the polling hook, the report table, the CSV
// writer - is behind this boundary, so someone who only reads the landing page
// never downloads it.
const AuditPage = lazy(() => import("./routes/AuditPage"));

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <ErrorBoundary>
            <Landing />
          </ErrorBoundary>
        }
      />
      <Route
        path="/audit"
        element={
          // Each route gets its own boundary, so a crash on one cannot take
          // the other down with it.
          <ErrorBoundary>
            <Suspense fallback={<div className="page page--narrow" aria-busy="true" />}>
              <AuditPage />
            </Suspense>
          </ErrorBoundary>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
