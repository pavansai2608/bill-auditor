import type React from "react";
import { useId, useState } from "react";

import { Chevron } from "./icons";
import { rupees } from "../lib/csv";
import { workingFor, type RoomRatio } from "../lib/arithmetic";
import type { LineVerdict, TraceEntry } from "../types";

interface Props {
  line: LineVerdict;
  trace: TraceEntry[];
  index: number;
  /** The report-level room ratio, where the second pass applied one. */
  ratio: RoomRatio | null;
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
export function LineRow({ line, trace, index, ratio }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const verdict = line.needs_human ? null : outcome(line);
  // The struck figure is the mark-up: it is only drawn where the policy
  // actually changed the number, so a full-price line carries no line through
  // it and the marked lines are the ones the eye finds.
  const marked = verdict !== null && (line.allowed ?? 0) < line.charged;
  const working = workingFor(line, ratio, trace);

  return (
    <>
      {/* The stagger index, capped: past the eighth row a per-row delay stops
          reading as sequence and starts reading as lag. */}
      <tr
        className={line.needs_human ? "flagged" : undefined}
        data-testid={`line-${index}`}
        style={{ "--row": Math.min(index, 8) } as React.CSSProperties}
      >
        <td data-label="Item">
          <span className="line-item">{line.item}</span>
        </td>
        <td className="num" data-label="Charged">
          {/* Struck where it was reduced. `del` rather than a class, because
              the strike is a statement about the figure and belongs in the
              markup a screen reader gets, not only in the paint. */}
          {marked ? (
            <del className="charged charged--struck">{rupees(line.charged)}</del>
          ) : (
            <span className="charged">{rupees(line.charged)}</span>
          )}
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
        <tr className="working-row">
          <td colSpan={6} id={panelId}>
            <div className="working">
              {/* The sum first, because it is the answer to the question the
                  chevron asks. The trace is the evidence under it. */}
              <div className="working-sum">
                <p className="working-headline">{working.headline}</p>
                <dl className="sum" data-testid={`sum-${index}`}>
                  {working.rows.map((row) => (
                    <div
                      key={row.label}
                      className={[
                        "sum-row",
                        row.rule ? "sum-row--ruled" : "",
                        row.result ? "sum-row--result" : "",
                        row.tone ? `sum-row--${row.tone}` : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      <dt>{row.label}</dt>
                      {/* The operator sits in its own column so the figures
                          stay in one rail, the way a sum is written out. */}
                      <dd className="sum-op" aria-hidden="true">
                        {row.op === "x" ? "×" : row.op === "-" ? "−" : ""}
                      </dd>
                      <dd className="sum-value">{row.value}</dd>
                    </div>
                  ))}
                </dl>
                {line.clause_id && (
                  <p className="working-clause">
                    under <span className="chip">{line.clause_id}</span>
                  </p>
                )}
              </div>

              <div className="working-trace">
                {/* The row clamps the reason to three lines, so the whole of
                    it has to be somewhere. Here, in full, above the trace it
                    summarises. */}
                <p className="label">Why, in full</p>
                <p className="working-reason">{line.reason}</p>
                <p className="label">What the system did</p>
                <div className="trace" data-testid={`trace-${index}`}>
                  {trace.length === 0 ? (
                    <div>no trace was recorded for this line</div>
                  ) : (
                    trace.map((entry, position) => (
                      <div key={position}>
                        {String(entry.node ?? "step").padEnd(18)}
                        {JSON.stringify(
                          Object.fromEntries(
                            Object.entries(entry).filter(
                              ([key]) => key !== "node" && key !== "item",
                            ),
                          ),
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
