import type { AuditReport } from "../types";

function cell(value: string | number | null): string {
  const text = value === null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** The report as a CSV a spreadsheet will open, flagged lines included. */
export function reportToCsv(report: AuditReport): string {
  const rows = [
    ["item", "charged", "allowed", "clause", "flagged", "reason"],
    ...report.lines.map((line) => [
      cell(line.item),
      cell(line.charged),
      cell(line.allowed === null ? "FLAGGED" : line.allowed),
      cell(line.clause_id),
      cell(line.needs_human ? "yes" : "no"),
      cell(line.reason),
    ]),
    [],
    ["total charged", cell(report.total_charged)],
    ["total payable", cell(report.total_allowed)],
    ["lines flagged", cell(report.flagged_count)],
  ];
  return rows.map((row) => row.join(",")).join("\n");
}

export function downloadCsv(report: AuditReport): void {
  const blob = new Blob([reportToCsv(report)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `bill-audit-${report.policy}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function rupees(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
}
