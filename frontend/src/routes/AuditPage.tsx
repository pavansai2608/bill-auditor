import { Suspense, lazy } from "react";
import { Link } from "react-router-dom";

import { BillForm } from "../components/BillForm";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { RunningPanel } from "../components/RunningPanel";
import { SubmittedSummary } from "../components/SubmittedSummary";
import { SkeletonReport } from "../components/Skeletons";
import { useAudit } from "../context/AuditContext";

// The report screen carries the table, the trace viewer and the CSV writer.
// None of that is needed to fill in the form, so it is split out and only
// fetched once there is something to show.
const ReportView = lazy(() => import("../components/ReportView"));
const CompareView = lazy(() => import("../components/CompareView"));

export default function AuditPage() {
  const { job } = useAudit();
  const status = job.status;
  const finished = status?.status === "done";

  return (
    <div className={finished ? "page audit-page" : "page page--narrow audit-page"}>
      <header className="masthead">
        <Link to="/" className="masthead-home">
          <span className="mark" aria-hidden="true" />
          <h1>Bill Auditor</h1>
        </Link>
      </header>
      <p className="explainer">
        Check a hospital bill against the policy that pays it, line by line, with the clause behind
        every deduction.
      </p>

      {job.error && (
        <div className="panel error" role="alert" data-testid="error-panel">
          <h2>The audit could not finish</h2>
          <p>{job.error}</p>
          <button type="button" className="btn-secondary" onClick={job.reset}>
            Start again
          </button>
        </div>
      )}

      {/* Each route gets its own boundary, so a crash in the report cannot
          take the form down with it. */}
      {!job.jobId && (
        <ErrorBoundary>
          <BillForm />
        </ErrorBoundary>
      )}

      {job.jobId && !job.error && <SubmittedSummary />}

      {job.jobId && !finished && !job.error && <RunningPanel />}

      {finished && (
        <ErrorBoundary>
          <Suspense fallback={<SkeletonReport />}>
            {job.kind === "audit" ? <ReportView /> : <CompareView />}
          </Suspense>
        </ErrorBoundary>
      )}
    </div>
  );
}
