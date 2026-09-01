import { AssumptionsPanel } from "./AssumptionsPanel";
import { LineRow } from "./LineRow";
import { useAudit } from "../context/AuditContext";
import { downloadCsv, rupees } from "../lib/csv";
import type { AuditReport, TraceEntry } from "../types";

/** Group the trace by the bill line it belongs to, so a row can show its own. */
function traceByItem(trace: TraceEntry[]): Map<string, TraceEntry[]> {
  const grouped = new Map<string, TraceEntry[]>();
  for (const entry of trace) {
    const item = typeof entry.item === "string" ? entry.item : null;
    if (!item) continue;
    const existing = grouped.get(item) ?? [];
    existing.push(entry);
    grouped.set(item, existing);
  }
  return grouped;
}

export default function ReportView() {
  const { form, job } = useAudit();
  const status = job.status;
  if (!status || status.status !== "done") return null;
  const report = status.report as AuditReport;

  const deducted = report.total_charged - report.total_allowed;
  const grouped = traceByItem(report.trace);

  return (
    <div data-testid="report">
      <section className="panel">
        <div className="summary">
          <div className="cell">
            <div className="label">Charged</div>
            <div className="value" data-testid="total-charged">
              {rupees(report.total_charged)}
            </div>
          </div>
          <div className="cell cell--deducted">
            <div className="label">Deducted</div>
            <div className="value" data-testid="total-deducted">
              {rupees(deducted)}
            </div>
          </div>
          <div className="cell">
            <div className="label">Payable</div>
            <div className="value" data-testid="total-allowed">
              {rupees(report.total_allowed)}
            </div>
          </div>
          <div className="cell cell--flagged">
            <div className="label">Flagged</div>
            <div className="value" data-testid="flagged-count">
              {report.flagged_count}
            </div>
          </div>
        </div>
      </section>

      <AssumptionsPanel assumptions={report.assumptions ?? []} />

      <section className="panel">
        <h2>Line by line</h2>
        <p className="panel-note">
          Every deduction names the clause that caused it. A flagged line is one no clause clearly
          covered, so it was not guessed at.
        </p>
        <table className="lines">
          <caption>
            {report.lines.length} lines audited against {report.policy.replace("_", " ")}
          </caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col" className="num">
                Charged
              </th>
              <th scope="col" className="num">
                Allowed
              </th>
              <th scope="col">Clause</th>
              <th scope="col">Why</th>
              <th scope="col">
                <span className="visually-hidden">Trace</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {report.lines.map((line, index) => (
              <LineRow
                key={`${line.item}-${index}`}
                line={line}
                index={index}
                trace={grouped.get(line.item) ?? []}
              />
            ))}
          </tbody>
        </table>
      </section>

      <div className="actions">
        <button
          type="button"
          className="btn-secondary"
          data-testid="compare"
          onClick={() => job.compare(form)}
        >
          Compare with other policies
        </button>
        <button
          type="button"
          className="btn-secondary"
          data-testid="download-csv"
          onClick={() => downloadCsv(report)}
        >
          Download CSV
        </button>
        <button type="button" className="btn-link" onClick={job.reset}>
          Audit another bill
        </button>
      </div>
    </div>
  );
}
