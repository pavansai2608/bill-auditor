import { useAudit } from "../context/AuditContext";
import { readBillItems } from "../lib/billStats";
import { SkeletonReport } from "./Skeletons";

/**
 * The wait, spent on the bill rather than on a spinner.
 *
 * An audit is minutes, not seconds, and a bar creeping from 0 to 100 over that
 * long says nothing except that something is still happening. What the person
 * actually wants to know is *which* line is being read, and the bill they
 * pasted is right here on the client - so the panel lists their own lines and
 * marks each one off as the server's done/total passes it.
 *
 * The counter is still the server's. `readBillItems` is the shy client reader,
 * not the parser, and it can find fewer lines than `core/bill.py` does; where
 * the two counts disagree the list is dropped entirely and the bar and the
 * counter carry the wait on their own. A list that named the wrong line would
 * be worse than no list, because it would be checked against the report later.
 *
 * A compare counts differently and the caption has to say so. Its total is
 * every line against every policy - a ten-line bill compared across three
 * policies is 30 - so calling that number "lines" reads as a parser fault on a
 * bill the reader can see has ten items. The number was always right; the noun
 * was not.
 */
export function RunningPanel() {
  const { form, job } = useAudit();
  const done = job.progress?.done ?? 0;
  const total = job.progress?.total ?? 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 4;
  const comparing = job.kind === "compare";
  const unit = comparing ? "line checks, one per policy" : "lines";

  // Only when this reading of the bill agrees with the server about how many
  // lines there are. A compare's total is a multiple of the line count, so the
  // list is an audit-only affordance.
  const items = readBillItems(form.billText);
  const named = !comparing && total > 0 && items.length === total ? items : null;

  return (
    <>
      <div className="panel running" data-testid="running-panel">
        <h2>{comparing ? "Reading every policy" : "Reading the policy"}</h2>
        <p className="panel-note">
          {comparing
            ? "Each line is checked against each policy separately, and the clause that decides it is recorded. Three policies take about three times as long as one."
            : "Each line is checked against the policy separately, and the clause that decides it is recorded. This takes a few minutes."}
        </p>
        <div className="progress">
          <div
            className="bar"
            role="progressbar"
            aria-valuenow={done}
            aria-valuemin={0}
            aria-valuemax={total || 1}
            aria-label={comparing ? "line checks completed" : "lines checked"}
          >
            <span style={{ transform: `scaleX(${percent / 100})` }} />
          </div>
          <p className="caption" aria-live="polite" data-testid="progress-caption">
            {total > 0 ? `checked ${done} of ${total} ${unit}` : "reading the bill"}
          </p>
        </div>

        {named && (
          <ol className="checklist" data-testid="running-lines">
            {named.map((item, index) => {
              // Done, being read now, or still to come. The server reports a
              // count, not a name, so "now" is inferred as the next line after
              // the ones it has finished - which is exactly what the count
              // means, since the lines are audited in order.
              const state = index < done ? "done" : index === done ? "now" : "waiting";
              return (
                <li key={`${item.description}-${index}`} className={`checklist-item is-${state}`}>
                  <span className="checklist-mark" aria-hidden="true" />
                  <span className="checklist-name">{item.description}</span>
                  <span className="checklist-amount num">
                    {item.amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </div>
      <SkeletonReport />
    </>
  );
}
