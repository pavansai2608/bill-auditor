/** Shown while the lazy report chunk loads, and while an audit is running. */
export function SkeletonReport() {
  return (
    <div data-testid="skeleton">
      <div className="panel">
        <div className="summary">
          {["charged", "deducted", "payable", "flagged"].map((cell) => (
            <div className="cell" key={cell}>
              <div className="skeleton skeleton-row" style={{ width: "60%", height: 12 }} />
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
