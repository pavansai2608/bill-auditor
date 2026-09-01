import { useAudit } from "../context/AuditContext";
import { rupees } from "../lib/csv";
import type { ComparisonReport } from "../types";

/** The same bill against every indexed policy. */
export default function CompareView() {
  const { job } = useAudit();
  const status = job.status;
  if (!status || status.status !== "done") return null;
  const comparison = status.report as ComparisonReport;

  return (
    <div data-testid="compare-report">
      <section className="panel">
        <h2>Which policy pays most</h2>
        <p className="panel-note">
          The same bill, audited three times. The spread is what the choice of insurer is worth on
          this bill: {rupees(comparison.difference)}.
        </p>
        <div className="compare">
          {comparison.reports.map((report) => (
            <div
              key={report.policy}
              className={report.policy === comparison.best_policy ? "panel best" : "panel"}
              data-testid={`compare-${report.policy}`}
            >
              <div className="label">{report.policy.replace("_", " ")}</div>
              <div className="value" style={{ fontSize: "var(--text-figure)", fontWeight: 600 }}>
                {rupees(report.total_allowed)}
              </div>
              <p className="panel-note">
                {report.flagged_count} flagged of {report.lines.length} lines
                {report.policy === comparison.best_policy ? " — pays most" : ""}
              </p>
            </div>
          ))}
        </div>
      </section>
      <div className="actions">
        <button type="button" className="btn-link" onClick={job.reset}>
          Audit another bill
        </button>
      </div>
    </div>
  );
}
