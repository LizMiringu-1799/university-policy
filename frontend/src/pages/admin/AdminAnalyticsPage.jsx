import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext.jsx";
import { adminAnalyticsApi } from "../../api/client.js";
import AppHeader from "../../components/AppHeader.jsx";
import Alert from "../../components/Alert.jsx";
import BarChart from "../../components/BarChart.jsx";
import LineChart from "../../components/LineChart.jsx";

// Date-range presets for the summary/volume section, listed as rows rather than a
// calendar — nobody fights a calendar grid for "last 30 days" (dataviz: interaction.md).
// Only scopes summary(): /documents and /ambiguous are all-time aggregates by design
// (implementation-plan.md §4.4 gives them no date params), so a preset above the whole
// page would misleadingly imply it filters the ranking sections too.
const RANGES = [
  { key: "all", label: "All time", days: null },
  { key: "7", label: "Last 7 days", days: 7 },
  { key: "30", label: "Last 30 days", days: 30 },
  { key: "90", label: "Last 90 days", days: 90 },
];

function rangeParams(key) {
  const range = RANGES.find((r) => r.key === key);
  if (!range?.days) return {};
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - (range.days - 1));
  const iso = (d) => d.toISOString().slice(0, 10);
  return { from: iso(from), to: iso(to) };
}

function formatMs(ms) {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

/** One headline number: label, value, optional muted note underneath. The figure
 * contract from dataviz (marks-and-anatomy.md) minus delta/trend — this dashboard's
 * stat tiles are a current snapshot, not a comparison against a prior period (there
 * isn't pilot history yet to compare against). */
function StatTile({ label, value, note }) {
  return (
    <div className="stat-tile">
      <span className="stat-tile-label">{label}</span>
      <span className="stat-tile-value">{value}</span>
      {note && <span className="stat-tile-note">{note}</span>}
    </div>
  );
}

/** Answered / unanswered / error as three stat tiles plus a proportion bar — the same
 * pattern as the Ratings page's helpful/not-helpful split, generalized to three status
 * outcomes instead of two. Status colors (good/warning/critical), not categorical: this
 * series literally means good-to-bad, which is exactly what status tokens are for. */
function OutcomeSummary({ summary }) {
  const total = summary.answered + summary.unanswered + summary.error;
  if (total === 0) {
    return <p className="subtitle">No queries in this range.</p>;
  }

  const segments = [
    { key: "answered", label: "Answered", count: summary.answered },
    { key: "unanswered", label: "Unanswered", count: summary.unanswered },
    { key: "error", label: "Error", count: summary.error },
  ].filter((s) => s.count > 0);

  return (
    <div className="rating-summary">
      <div className="rating-summary-tiles">
        {segments.map((s) => (
          <div className="rating-summary-tile" key={s.key}>
            <span className={`rating-summary-dot outcome-dot-${s.key}`} aria-hidden="true" />
            <span className="rating-summary-label">{s.label}</span>
            <span className="rating-summary-value">{Math.round((s.count / total) * 100)}%</span>
            <span className="rating-summary-count">
              {s.count} {s.count === 1 ? "query" : "queries"}
            </span>
          </div>
        ))}
      </div>
      <div
        className="rating-summary-bar"
        role="img"
        aria-label={segments.map((s) => `${s.label} ${Math.round((s.count / total) * 100)}%`).join(", ")}
      >
        {segments.map((s) => {
          const pct = Math.round((s.count / total) * 100);
          return (
            <div
              key={s.key}
              className={`rating-summary-segment outcome-segment-${s.key}`}
              style={{ width: `${pct}%` }}
              title={`${s.label}: ${s.count} (${pct}%)`}
            >
              {pct >= 15 && <span>{pct}%</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** One ambiguous-policy row: the numbers plus a few example questions that triggered
 * it. Rendered as a card list rather than a chart — this many distinct fields per item
 * reads better as a table than as marks on an axis (dataviz: choosing-a-form.md). */
function AmbiguousRow({ item }) {
  return (
    <div className="ambiguous-row">
      <div className="ambiguous-row-header">
        <span className="ambiguous-title">{item.title}</span>
        <span className="ambiguous-cite-rate" title="Of the times this policy was retrieved, the share that ended up cited">
          {Math.round(item.cite_rate * 100)}% cited
        </span>
      </div>
      <div className="ambiguous-stats">
        <span>{item.times_retrieved} retrieved</span>
        <span>{item.times_cited} cited</span>
        <span>{Math.round(item.mean_similarity * 100)}% mean similarity</span>
        <span>{item.unanswered_queries} unanswered</span>
      </div>
      {item.sample_queries.length > 0 && (
        <ul className="ambiguous-samples">
          {item.sample_queries.map((q, i) => (
            <li key={i}>"{q}"</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Admin analytics dashboard (objective 5): query volume over time, answered-vs-
 * unanswered-vs-error rate, most-queried policies, and most-ambiguous policies — all
 * read live off query_logs/query_retrievals, no separate logging of its own
 * (implementation-plan.md §4.4, §5). The date-range preset only scopes the top section;
 * the two ranking sections below are all-time by design (see RANGES above).
 */
export default function AdminAnalyticsPage() {
  const { token } = useAuth();
  const [range, setRange] = useState("30");
  const [summary, setSummary] = useState(null);
  const [documentStats, setDocumentStats] = useState([]);
  const [ambiguous, setAmbiguous] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      adminAnalyticsApi.summary(rangeParams(range), token),
      adminAnalyticsApi.documents(token),
      adminAnalyticsApi.ambiguous({ limit: 10 }, token),
    ])
      .then(([summaryData, documentsData, ambiguousData]) => {
        setSummary(summaryData);
        setDocumentStats(documentsData);
        setAmbiguous(ambiguousData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [range, token]);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="admin-main analytics-main">
        <h1>Analytics</h1>

        <Alert>{error}</Alert>

        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : (
          summary && (
            <>
              <div className="analytics-filters">
                {RANGES.map((r) => (
                  <button
                    key={r.key}
                    type="button"
                    className={`analytics-filter${range === r.key ? " active" : ""}`}
                    onClick={() => setRange(r.key)}
                  >
                    {r.label}
                  </button>
                ))}
              </div>

              <div className="analytics-stat-row">
                <StatTile label="Total queries" value={summary.total_queries} />
                <StatTile label="Distinct users" value={summary.distinct_users} />
                <StatTile
                  label="Avg. confidence"
                  value={summary.avg_confidence != null ? `${Math.round(summary.avg_confidence * 100)}%` : "—"}
                />
                <StatTile label="Avg. response time" value={formatMs(summary.avg_response_ms)} />
              </div>

              <section className="analytics-section">
                <h2>Query volume</h2>
                <LineChart points={summary.queries_per_day} label="Queries" />
              </section>

              <section className="analytics-section">
                <h2>Answered vs. unanswered vs. error</h2>
                <OutcomeSummary summary={summary} />
              </section>

              <section className="analytics-section">
                <h2>Most-queried policies</h2>
                {documentStats.length === 0 ? (
                  <p className="subtitle">No retrievals logged yet.</p>
                ) : (
                  <BarChart
                    items={documentStats.slice(0, 10)}
                    valueKey="times_retrieved"
                    formatDetail={(item) =>
                      `${item.title}: retrieved ${item.times_retrieved} time${item.times_retrieved === 1 ? "" : "s"}, cited ${item.times_cited}`
                    }
                  />
                )}
              </section>

              <section className="analytics-section">
                <h2>Most-ambiguous policies</h2>
                <p className="subtitle">Retrieved often, cited rarely — a sign the policy is missing, unclear, or poorly matched.</p>
                {ambiguous.length === 0 ? (
                  <p className="subtitle">Not enough data yet to tell.</p>
                ) : (
                  <div className="ambiguous-list">
                    {ambiguous.map((item) => (
                      <AmbiguousRow key={item.document_id} item={item} />
                    ))}
                  </div>
                )}
              </section>
            </>
          )
        )}
      </main>
    </div>
  );
}
