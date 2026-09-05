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

/**
 * The bill, split three ways.
 *
 * `total_allowed` already counts a flagged line as zero, so the three parts
 * add up to what was charged: what the policy pays, what a clause took off,
 * and what nothing covered clearly enough to decide either way. The third is
 * separated out because it is not a deduction - it is an open question, and
 * showing it inside "deducted" would tell the reader they had lost money that
 * nobody has actually refused yet.
 */
function split(report: AuditReport) {
  const flagged = report.lines
    .filter((line) => line.needs_human)
    .reduce((sum, line) => sum + line.charged, 0);
  const payable = report.total_allowed;
  const reduced = Math.max(report.total_charged - payable - flagged, 0);
  return { payable, reduced, flagged };
}

function percent(part: number, whole: number): string {
  if (whole <= 0) return "0%";
  return `${(part / whole) * 100}%`;
}

export default function ReportView() {
  const { form, job } = useAudit();
  const status = job.status;
  if (!status || status.status !== "done") return null;
  const report = status.report as AuditReport;

  const { payable, reduced, flagged } = split(report);
  const deducted = report.total_charged - report.total_allowed;
  const grouped = traceByItem(report.trace);
  const flaggedLines = report.flagged_count;

  return (
    <div data-testid="report">
      {/* The whole answer, to scale, before a single row is read. */}
      <section className="verdict" aria-labelledby="verdict-heading">
        <h2 id="verdict-heading" className="visually-hidden">
          What the policy pays on this bill
        </h2>

        {/* The head is context - what went in. The figures under the bar are
            the answer, and the deducted one is set largest of all of them. */}
        <div className="verdict-head">
          <div className="verdict-charged">
            <span className="label">Charged</span>
            <span className="value" data-testid="total-charged">
              {rupees(report.total_charged)}
            </span>
          </div>
          <span className="verdict-policy">
            {report.lines.length} lines against {report.policy.replace(/_/g, " ")}
          </span>
        </div>

        <div className="verdict-bar" role="presentation">
          <span className="seg-paid" style={{ flexBasis: percent(payable, report.total_charged) }} />
          <span className="seg-cut" style={{ flexBasis: percent(reduced, report.total_charged) }} />
          <span className="seg-flag" style={{ flexBasis: percent(flagged, report.total_charged) }} />
        </div>

        <div className="verdict-key">
          <div className="key-paid">
            <span className="label">Payable</span>
            <span className="value" data-testid="total-allowed">
              {rupees(payable)}
            </span>
            <span className="note">what the policy pays, with a clause behind every line</span>
          </div>
          <div className="key-cut">
            <span className="label">Deducted</span>
            <span className="value" data-testid="total-deducted">
              {rupees(deducted)}
            </span>
            <span className="note">
              {rupees(reduced)} cut by a clause
              {flagged > 0 ? `, ${rupees(flagged)} on flagged lines` : ""}
            </span>
          </div>
          <div className="key-flag">
            <span className="label">Flagged</span>
            <span className="value" data-testid="flagged-count">
              {flaggedLines}
            </span>
            <span className="note">
              {flaggedLines === 1 ? "line had" : "lines had"} no clause that clearly applied — for a
              person to check, never guessed at
            </span>
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
