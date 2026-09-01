import type { Assumption } from "../types";

/**
 * Always visible, never behind a toggle. The system assumed something it could
 * not verify, and hiding that behind a click would make the report look more
 * certain than it is.
 */
export function AssumptionsPanel({ assumptions }: { assumptions: Assumption[] }) {
  if (assumptions.length === 0) return null;
  return (
    <section className="panel assumptions" data-testid="assumptions">
      <h2>Assumptions</h2>
      <p className="panel-note">Things the audit took on trust because no input could prove them.</p>
      <ul>
        {assumptions.map((assumption) => (
          <li key={assumption.assumption}>
            <div>{assumption.statement}</div>
            <div className="because">
              because {assumption.because}
              {assumption.clause_id ? ` (clause ${assumption.clause_id})` : ""}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
