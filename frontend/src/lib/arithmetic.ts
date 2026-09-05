/**
 * The sum behind a deduction, laid out so a person can check it.
 *
 * "Why the room rent came down by Rs 15,000" is not a sentence, it is a
 * calculation, and the report's whole claim is that every deduction is one
 * somebody could redo by hand. So this turns a `LineVerdict` into the rows of
 * that calculation - a cap, a count, a multiplication, a subtraction - rather
 * than into prose describing it.
 *
 * ---------------------------------------------------------------------------
 * What the API does NOT send, and what is therefore derived here
 * ---------------------------------------------------------------------------
 * `LineVerdict` (core/models.py) carries item, charged, allowed, clause_id,
 * reason, needs_human, over_limit and limit_per_day. It does NOT carry:
 *
 *   - the number of days a per-day cap was applied over;
 *   - the ratio the second pass used on an associated line;
 *   - any record of which arithmetic actually ran.
 *
 * Both of the first two are recoverable from figures that ARE sent, and both
 * are recovered here under the same rule: **derive it, then check it against
 * the allowed figure the server computed, and only state it if it reconciles
 * exactly.** A derivation that does not reproduce the server's own number is
 * discarded and the line falls back to the plain charged-minus-allowed form.
 *
 * That rule matters more than the feature. This panel exists to be checked; a
 * plausible-looking day count that is not the one the server used would be a
 * confident wrong answer on a page about someone's medical costs, which is
 * precisely the failure the rest of this system is built to avoid. Where the
 * working cannot be shown honestly, it is not shown.
 */
import type { LineVerdict, TraceEntry } from "../types";

/** A row of the sum: a name on the left, a figure on the right. */
export interface WorkingRow {
  /** What this figure is. */
  label: string;
  /** The figure itself, already formatted. */
  value: string;
  /** The operator that applies this row to the one above it. */
  op?: "x" | "-";
  /** A rule above this row, the way a total is ruled off on paper. */
  rule?: boolean;
  /** The result line: set larger, and coloured by what happened. */
  result?: boolean;
  tone?: "cut" | "paid";
}

export interface Working {
  /** Which shape of explanation this is; drives the heading. */
  kind: "per_day_cap" | "proportionate" | "not_payable" | "reduced" | "paid" | "flagged";
  /** One sentence naming the mechanism, in the product's own words. */
  headline: string;
  rows: WorkingRow[];
}

/** The ratio the second pass applied, recovered from the room-rent line. */
export interface RoomRatio {
  /** Eligible room rent divided by room rent actually incurred. */
  ratio: number;
  /** What the room was billed at, per day. */
  chargedPerDay: number;
  /** What the policy allowed, per day. */
  limitPerDay: number;
}

const MAX_DAYS = 366;
/** Rupee figures are whole rupees, so a reconciliation is exact to within one. */
const TOLERANCE = 1;

function money(value: number): string {
  return value.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

/**
 * How many days a per-day cap was applied over, or null.
 *
 * `allowed` is the cap times the days, so the days divide out - but only if
 * the cap is what bound this line. A line reduced by something else entirely
 * would still produce a number here, so the quotient has to be a whole count
 * of days that reproduces `allowed` exactly before it is believed.
 */
export function daysFromCap(allowed: number, limitPerDay: number): number | null {
  if (!(limitPerDay > 0) || !(allowed > 0)) return null;
  const days = allowed / limitPerDay;
  if (!Number.isInteger(days)) return null;
  if (days < 1 || days > MAX_DAYS) return null;
  return days;
}

/**
 * The ratio the second pass used, and the two figures it came from.
 *
 * The report states the ratio itself: `core/second_pass.py` writes a
 * report-level trace entry `{node: "second_pass", applied: true, ratio: 0.625,
 * because: "<the room line>"}`. That is the authority, because it is the
 * number the server actually multiplied by.
 *
 * The per-day figures either side of it are not stated anywhere, so they are
 * read off the room line named by `because` - eligible over incurred - and the
 * pair is only returned if the room line reproduces the stated ratio. Where
 * the trace carries no ratio the room line supplies one on its own, under the
 * same reconciliation. Either way the ratio shown is one the report can be
 * checked against, never one invented to fill the panel.
 */
export function roomRatio(lines: LineVerdict[], trace: TraceEntry[]): RoomRatio | null {
  const stated = trace.find(
    (entry) => entry.node === "second_pass" && entry.applied === true && !entry.item,
  );
  const statedRatio = typeof stated?.ratio === "number" ? stated.ratio : null;
  const namedItem = typeof stated?.because === "string" ? stated.because : null;

  const capped = (line: LineVerdict) =>
    line.limit_per_day !== null &&
    line.limit_per_day > 0 &&
    line.allowed !== null &&
    line.allowed > 0 &&
    line.charged > line.allowed;

  // The line the trace names, when it names one; otherwise the capped room
  // line, which is the only kind of line that can drive this deduction.
  const room =
    (namedItem ? lines.find((line) => line.item === namedItem && capped(line)) : undefined) ??
    lines.find((line) => line.over_limit && capped(line));

  if (!room || room.allowed === null || room.limit_per_day === null) return null;

  const days = daysFromCap(room.allowed, room.limit_per_day);
  if (days === null) return null;

  const derived = room.allowed / room.charged;
  // If the report stated a ratio, the room line has to agree with it before
  // either number is put in front of someone.
  if (statedRatio !== null && Math.abs(statedRatio - derived) > 0.0001) return null;

  return {
    ratio: statedRatio ?? derived,
    chargedPerDay: room.charged / days,
    limitPerDay: room.limit_per_day,
  };
}

/** A percentage a reader can check, without a run of meaningless decimals. */
function percent(ratio: number): string {
  const scaled = ratio * 100;
  const rounded = Math.round(scaled * 100) / 100;
  return `${rounded}%`;
}

/**
 * The sum behind one line.
 *
 * `ratio` is the report-level room ratio when there is one, and `trace` is
 * this line's own trace. The proportionate form is used only when the trace
 * says this line was rescaled AND the ratio reproduces its allowed figure -
 * two independent confirmations, because naming the wrong mechanism beside a
 * real figure is the failure mode that matters here.
 */
export function workingFor(
  line: LineVerdict,
  ratio: RoomRatio | null,
  trace: TraceEntry[] = [],
): Working {
  const charged = line.charged;
  const allowed = line.allowed;

  if (line.needs_human || allowed === null) {
    return {
      kind: "flagged",
      headline: "No clause clearly applied to this line, so nothing was decided.",
      rows: [{ label: "Charged", value: money(charged) }],
    };
  }

  if (allowed >= charged) {
    return {
      kind: "paid",
      headline: "Nothing was taken off this line.",
      rows: [
        { label: "Charged", value: money(charged) },
        { label: "Allowed", value: money(allowed), rule: true, result: true, tone: "paid" },
      ],
    };
  }

  const removed = charged - allowed;

  // A per-day cap: the one deduction the report can show in full, because the
  // cap is sent and the day count divides out of the allowed figure.
  if (line.limit_per_day !== null && line.limit_per_day > 0) {
    const days = daysFromCap(allowed, line.limit_per_day);
    if (days !== null) {
      return {
        kind: "per_day_cap",
        headline: `The policy caps this at ${money(line.limit_per_day)} a day.`,
        rows: [
          { label: "Cap, per day", value: money(line.limit_per_day) },
          { label: days === 1 ? "Day billed" : "Days billed", value: String(days), op: "x" },
          { label: "Eligible", value: money(allowed), rule: true },
          { label: "Charged", value: money(charged) },
          { label: "Removed", value: money(removed), op: "-", rule: true, result: true, tone: "cut" },
        ],
      };
    }
  }

  // Nothing at all was allowed. There is no working to show beyond the fact,
  // and the clause beside it is the whole of the answer.
  if (allowed === 0) {
    return {
      kind: "not_payable",
      headline: "The clause below excludes this line entirely.",
      rows: [
        { label: "Charged", value: money(charged) },
        { label: "Allowed", value: money(0) },
        { label: "Removed", value: money(removed), op: "-", rule: true, result: true, tone: "cut" },
      ],
    };
  }

  // The proportionate deduction. The trace has to say this line was rescaled
  // and the ratio has to reproduce its allowed figure; either alone is not
  // enough, because a line can be reduced to the same number by a cap that has
  // nothing to do with the room. B01's ambulance line is exactly that - it
  // lands on Rs 750 under a per-hospitalization cap, not on 62.5% of Rs 1,000
  // - and it is this check that keeps the room out of its explanation.
  const rescaled = trace.some(
    (entry) => entry.node === "second_pass" && entry.item === line.item && entry.rescaled === true,
  );
  if (ratio && rescaled && Math.abs(charged * ratio.ratio - allowed) <= TOLERANCE) {
    return {
      kind: "proportionate",
      headline:
        `The room was billed at ${money(ratio.chargedPerDay)} a day against a ` +
        `${money(ratio.limitPerDay)} limit, so ${percent(ratio.ratio)} of this line is eligible too.`,
      rows: [
        { label: "Charged", value: money(charged) },
        { label: "Eligible share", value: percent(ratio.ratio), op: "x" },
        { label: "Allowed", value: money(allowed), rule: true },
        { label: "Removed", value: money(removed), op: "-", rule: true, result: true, tone: "cut" },
      ],
    };
  }

  // Reduced, by something this report does not state in figures. The
  // subtraction is still shown, because it is still true; the mechanism is
  // left to the clause and the reason rather than invented here.
  return {
    kind: "reduced",
    headline: "The clause below allowed part of this line.",
    rows: [
      { label: "Charged", value: money(charged) },
      { label: "Allowed", value: money(allowed) },
      { label: "Removed", value: money(removed), op: "-", rule: true, result: true, tone: "cut" },
    ],
  };
}
