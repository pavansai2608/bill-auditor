/**
 * The icon set. Three marks, drawn here rather than typed as characters.
 *
 * A "+" in the markup is a glyph from whatever face the browser resolved, at
 * whatever weight that face happens to have; it cannot be rotated, cannot
 * inherit a stroke, and looks different on every machine. These are authored
 * paths on one grid at one stroke weight, so the toggle, the arrow and the
 * wordmark are visibly the same hand.
 *
 * Every one is presentational: the label lives on the element that carries
 * the icon, so each is hidden from assistive technology.
 */

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/**
 * The wordmark: a sheet of paper with three ruled lines and one stroke
 * through them. A bill, and a deduction taken off it.
 */
export function Mark({ className = "mark" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" aria-hidden="true" focusable="false" {...stroke}>
      <rect x="3.5" y="1.75" width="13" height="16.5" rx="2.25" />
      <path d="M6.9 6.9h6.2M6.9 10.4h6.2M6.9 13.9h3.4" />
      <path d="M5.6 15.9 14.4 8.4" strokeWidth={1.75} />
    </svg>
  );
}

/** On the primary action, and it moves on hover. */
export function ArrowRight() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" {...stroke}>
      <path d="M2.5 8h11M9.5 4l4 4-4 4" />
    </svg>
  );
}

/** The trace disclosure. The rule that turns it is in styles.css. */
export function Chevron() {
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true" focusable="false" {...stroke}>
      <path d="M3.5 5.5 7 9l3.5-3.5" />
    </svg>
  );
}
