import { useId, useState } from "react";

import { Chevron } from "./icons";
import { rupees } from "../lib/csv";
import type { LineVerdict, TraceEntry } from "../types";

interface Props {
  line: LineVerdict;
  trace: TraceEntry[];
  index: number;
}

/**
 * What happened to one line, in one word.
 *
 * The colour is the fast read and the word is the answer: someone who cannot
 * tell the green from the crimson still gets "paid in full" or "-Rs 15,000"
 * in text under the figure, and a flagged line says so rather than relying on
 * a tinted row.
 */
function outcome(line: LineVerdict): { tone: "paid" | "cut"; note: string } {
  const allowed = line.allowed ?? 0;
  if (allowed >= line.charged) return { tone: "paid", note: "paid in full" };
  if (allowed === 0) return { tone: "cut", note: "not payable" };
  return { tone: "cut", note: `−${rupees(line.charged - allowed)}` };
}

/** One bill line, expandable to show exactly how it was decided. */
export function LineRow({ line, trace, index }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const verdict = line.needs_human ? null : outcome(line);

  return (
    <>
      <tr className={line.needs_human ? "flagged" : undefined} data-testid={`line-${index}`}>
        <td data-label="Item">
          <span className="line-item">{line.item}</span>
        </td>
        <td className="num" data-label="Charged">
          {rupees(line.charged)}
        </td>
        <td className="num" data-label="Allowed" data-testid={`allowed-${index}`}>
          {verdict === null ? (
            <span className="chip chip--flag">needs a person</span>
          ) : (
            <span className="allowed-cell">
              <span className={`allowed allowed--${verdict.tone}`}>{rupees(line.allowed)}</span>
              <span className={verdict.tone === "paid" ? "delta delta--paid" : "delta"}>
                {verdict.note}
              </span>
            </span>
          )}
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
            <Chevron />
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
