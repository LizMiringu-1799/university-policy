import { useId, useMemo, useState } from "react";

const WIDTH = 600;
const HEIGHT = 200;
const PAD_LEFT = 36;
const PAD_RIGHT = 12;
const PAD_TOP = 16;
const PAD_BOTTOM = 24;

/** Every calendar day between the first and last day present in `points`
 * ({date: "YYYY-MM-DD", count}), zero-filling any day with no rows — otherwise a quiet
 * stretch collapses to nothing and the x-axis spacing stops meaning "one day apart". */
function fillGaps(points) {
  if (points.length === 0) return [];
  const byDate = new Map(points.map((p) => [p.date, p.count]));
  const start = new Date(points[0].date);
  const end = new Date(points[points.length - 1].date);
  const filled = [];
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const date = d.toISOString().slice(0, 10);
    filled.push({ date, count: byDate.get(date) ?? 0 });
  }
  return filled;
}

function formatDate(iso) {
  const [, m, d] = iso.split("-");
  return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m) - 1]} ${Number(d)}`;
}

/**
 * Query volume over time: a single-series line (one hue, no legend needed — the title
 * names the series). A vertical crosshair tracks the pointer and snaps to the nearest
 * day, with a tooltip carrying the date and count; the same pair is also reachable as
 * a visible axis plus the raw `points` the caller already has, so nothing is hover-only.
 */
export default function LineChart({ points, label = "Queries" }) {
  const gradientId = useId();
  const [hoverIndex, setHoverIndex] = useState(null);
  const data = useMemo(() => fillGaps(points), [points]);

  if (data.length === 0) {
    return <p className="subtitle">No data in this range.</p>;
  }

  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const xFor = (i) => PAD_LEFT + (data.length === 1 ? plotWidth / 2 : (i / (data.length - 1)) * plotWidth);
  const yFor = (count) => PAD_TOP + plotHeight - (count / maxCount) * plotHeight;

  const linePath = data.map((d, i) => `${i === 0 ? "M" : "L"} ${xFor(i).toFixed(1)} ${yFor(d.count).toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L ${xFor(data.length - 1).toFixed(1)} ${(PAD_TOP + plotHeight).toFixed(1)} L ${xFor(0).toFixed(1)} ${(PAD_TOP + plotHeight).toFixed(1)} Z`;

  // Y-axis ticks: 0, half, and the rounded max, so the reader has a scale without a
  // number crowding every gridline.
  const yTicks = [0, Math.round(maxCount / 2), maxCount];

  function handleMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * WIDTH;
    const ratio = data.length === 1 ? 0 : (x - PAD_LEFT) / plotWidth;
    const index = Math.max(0, Math.min(data.length - 1, Math.round(ratio * (data.length - 1))));
    setHoverIndex(index);
  }

  const hovered = hoverIndex != null ? data[hoverIndex] : null;

  return (
    <div className="line-chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="line-chart-svg"
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
        role="img"
        aria-label={`${label} over time, from ${formatDate(data[0].date)} to ${formatDate(data[data.length - 1].date)}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.1" />
            <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={PAD_LEFT}
              x2={WIDTH - PAD_RIGHT}
              y1={yFor(tick)}
              y2={yFor(tick)}
              className="line-chart-gridline"
            />
            <text x={PAD_LEFT - 8} y={yFor(tick)} className="line-chart-tick" textAnchor="end" dominantBaseline="middle">
              {tick}
            </text>
          </g>
        ))}

        <path d={areaPath} fill={`url(#${gradientId})`} />
        <path d={linePath} className="line-chart-line" fill="none" />

        {hovered && (
          <>
            <line
              x1={xFor(hoverIndex)}
              x2={xFor(hoverIndex)}
              y1={PAD_TOP}
              y2={PAD_TOP + plotHeight}
              className="line-chart-crosshair"
            />
            <circle cx={xFor(hoverIndex)} cy={yFor(hovered.count)} r="4" className="line-chart-dot" />
          </>
        )}
      </svg>

      {hovered && (
        <div
          className="line-chart-tooltip"
          style={{ left: `${(xFor(hoverIndex) / WIDTH) * 100}%` }}
        >
          <strong>{hovered.count}</strong> {label.toLowerCase()} · {formatDate(hovered.date)}
        </div>
      )}
    </div>
  );
}
