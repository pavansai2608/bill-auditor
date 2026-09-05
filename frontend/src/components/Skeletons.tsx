/** Shown while the lazy report chunk loads, and while an audit is running. */
export function SkeletonReport() {
  return (
    <div data-testid="skeleton">
      {/* The same shape the verdict band will take, so nothing jumps when the
          figures arrive: a head, the bar, and three columns under it. */}
      <div className="verdict">
        <div className="verdict-head">
          <div className="skeleton" style={{ height: 22, width: 200 }} />
        </div>
        <div className="skeleton" style={{ height: 14, borderRadius: 999 }} />
        <div className="verdict-key">
          {["payable", "deducted", "flagged"].map((cell) => (
            <div key={cell}>
              <div className="skeleton skeleton-row" style={{ width: "50%", height: 11 }} />
              <div className="skeleton" style={{ height: 34, width: "80%" }} />
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        {[0, 1, 2, 3, 4, 5].map((row) => (
          <div className="skeleton skeleton-row" key={row} style={{ width: `${95 - row * 6}%` }} />
        ))}
      </div>
    </div>
  );
}
