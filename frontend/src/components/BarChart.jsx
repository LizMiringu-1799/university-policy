/**
 * Horizontal magnitude bars: one hue (this is "how much", not "which one" — sequential,
 * not categorical), label to the left, value at the bar's tip rather than crowded
 * inside it (always room out there, unlike inside a short bar). Each bar is its own
 * hover/focus target carrying the full detail line as a tooltip, so nothing shown only
 * on hover is unreachable otherwise — the value at the tip already carries the headline
 * number without hovering at all.
 */
export default function BarChart({ items, valueKey, labelKey = "title", formatDetail }) {
  if (items.length === 0) {
    return <p className="subtitle">No data yet.</p>;
  }

  const max = Math.max(...items.map((item) => item[valueKey]), 1);

  return (
    <div className="bar-chart" role="table" aria-label="Ranked by value">
      {items.map((item, i) => (
        <div
          className="bar-chart-row"
          key={item.id ?? item[labelKey] ?? i}
          title={formatDetail ? formatDetail(item) : undefined}
        >
          <span className="bar-chart-label" title={item[labelKey]}>
            {item[labelKey]}
          </span>
          <div className="bar-chart-track">
            <div className="bar-chart-fill" style={{ width: `${Math.max((item[valueKey] / max) * 100, 2)}%` }} />
          </div>
          <span className="bar-chart-value">{item[valueKey]}</span>
        </div>
      ))}
    </div>
  );
}
