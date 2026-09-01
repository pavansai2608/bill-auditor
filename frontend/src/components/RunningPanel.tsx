import { useAudit } from "../context/AuditContext";
import { SkeletonReport } from "./Skeletons";

/**
 * An audit takes 30-60 seconds, so this has to say something true the whole
 * time rather than spin. The counter comes from the API's own done/total.
 */
export function RunningPanel() {
  const { job } = useAudit();
  const done = job.progress?.done ?? 0;
  const total = job.progress?.total ?? 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 4;

  return (
    <>
      <div className="panel" data-testid="running-panel">
        <h2>Reading the policy</h2>
        <p className="panel-note">
          Each line is checked against the policy separately, and the clause that decides it is
          recorded. This usually takes under a minute.
        </p>
        <div className="progress">
          <div
            className="bar"
            role="progressbar"
            aria-valuenow={done}
            aria-valuemin={0}
            aria-valuemax={total || 1}
            aria-label="lines checked"
          >
            <span style={{ width: `${percent}%` }} />
          </div>
          <p className="caption" aria-live="polite" data-testid="progress-caption">
            {total > 0 ? `checked ${done} of ${total} lines` : "reading the bill"}
          </p>
        </div>
      </div>
      <SkeletonReport />
    </>
  );
}
