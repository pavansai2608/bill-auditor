import { useAudit } from "../context/AuditContext";
import { SkeletonReport } from "./Skeletons";

/**
 * An audit takes 30-60 seconds, so this has to say something true the whole
 * time rather than spin. The counter comes from the API's own done/total.
 *
 * A compare counts differently and the caption has to say so. Its total is
 * every line against every policy - a ten-line bill compared across three
 * policies is 30 - so calling that number "lines" reads as a parser fault on a
 * bill the reader can see has ten items. The number was always right; the noun
 * was not.
 */
export function RunningPanel() {
  const { job } = useAudit();
  const done = job.progress?.done ?? 0;
  const total = job.progress?.total ?? 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 4;
  const comparing = job.kind === "compare";
  const unit = comparing ? "line checks, one per policy" : "lines";

  return (
    <>
      <div className="panel" data-testid="running-panel">
        <h2>{comparing ? "Reading every policy" : "Reading the policy"}</h2>
        <p className="panel-note">
          {comparing
            ? "Each line is checked against each policy separately, and the clause that decides it is recorded. Three policies take about three times as long as one."
            : "Each line is checked against the policy separately, and the clause that decides it is recorded. This usually takes under a minute."}
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
      </div>
      <SkeletonReport />
    </>
  );
}
