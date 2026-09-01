import { useId, useState } from "react";

import { rupees } from "../lib/csv";
import type { LineVerdict, TraceEntry } from "../types";

interface Props {
  line: LineVerdict;
  trace: TraceEntry[];
  index: number;
}

/** One bill line, expandable to show exactly how it was decided. */
export function LineRow({ line, trace, index }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <>
      <tr className={line.needs_human ? "flagged" : undefined} data-testid={`line-${index}`}>
        <td data-label="Item">{line.item}</td>
        <td className="num" data-label="Charged">
          {rupees(line.charged)}
        </td>
        <td className="num" data-label="Allowed" data-testid={`allowed-${index}`}>
          {line.needs_human ? <span className="chip chip--flag">flagged</span> : rupees(line.allowed)}
        </td>
        <td data-label="Clause">
          {line.clause_id ? (
            <span className="chip">{line.clause_id}</span>
          ) : (
            <span className="chip chip--none">none</span>
          )}
        </td>
        <td data-label="Why">
          <div className="reason">{line.reason}</div>
        </td>
        <td data-label="Trace">
          <button
            type="button"
            className="row-toggle"
            aria-expanded={open}
            aria-controls={panelId}
            aria-label={`how ${line.item} was decided`}
            data-testid={`trace-toggle-${index}`}
            onClick={() => setOpen(!open)}
          >
            {open ? "−" : "+"}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} id={panelId}>
            <div className="trace" data-testid={`trace-${index}`}>
              {trace.length === 0 ? (
                <div>no trace was recorded for this line</div>
              ) : (
                trace.map((entry, position) => (
                  <div key={position}>
                    {String(entry.node ?? "step").padEnd(18)}
                    {JSON.stringify(
                      Object.fromEntries(
                        Object.entries(entry).filter(([key]) => key !== "node" && key !== "item"),
                      ),
                    )}
                  </div>
                ))
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
