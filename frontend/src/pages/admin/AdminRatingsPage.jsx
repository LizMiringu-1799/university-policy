import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { adminRatingsApi } from "../../api/client.js";
import AppHeader from "../../components/AppHeader.jsx";
import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import ThumbIcon from "../../components/ThumbIcon.jsx";
import { formatDate } from "../../utils/date.js";

const PER_PAGE = 20;

// The two tabs this page separates ratings into, so "how many liked it" and "how many
// didn't" are never scanned off one blended list. No "All" tab, matching the same
// choice on Student Questions: a rating is always exactly one or the other.
const TABS = [
  { rating: "up", label: "Helpful", down: false },
  { rating: "down", label: "Not helpful", down: true },
];

/** One rated answer: the question and system answer it belongs to, who rated it, and
 * their comment if they left one. Distinct from the card on the Student Questions
 * page — this shows every rating, not just the ones that got escalated. The rating
 * itself isn't repeated here since the active tab already says which kind this is. */
function RatingCard({ item }) {
  return (
    <div className={`rating-card rating-card-${item.rating}`}>
      <div className="escalation-card-header">
        <span className="escalation-date">{formatDate(item.created_at)}</span>
        {item.query?.document && (
          <Link to={`/policies/${item.query.document.id}`} className="rating-document-link">
            {item.query.document.title}
          </Link>
        )}
      </div>

      <p className="escalation-meta">{item.student?.name || "Unknown user"}</p>

      {item.query ? (
        <>
          <p className="escalation-question">{item.query.question}</p>
          <div className="escalation-system-answer">
            <h4>System's answer</h4>
            <p>{item.query.answer_md}</p>
            {item.query.confidence != null && (
              <span className="ai-confidence">confidence {Math.round(item.query.confidence * 100)}%</span>
            )}
          </div>
        </>
      ) : (
        <p className="subtitle">The rated question has since been removed.</p>
      )}

      {item.comment && (
        <div className="rating-comment">
          <h4>Comment</h4>
          <p>"{item.comment}"</p>
        </div>
      )}
    </div>
  );
}

/**
 * Overall usefulness of the system, as rated by students and staff: two stat tiles
 * (% helpful, % not helpful, each with its raw count) and a proportion bar underneath
 * as a visual read of the same split. Always computed off `counts`, the unfiltered
 * up/down totals — the split doesn't change as the list below is filtered, since the
 * question this answers is "how is the system doing overall," not "how is it doing
 * among the ratings currently shown."
 */
function RatingSummary({ counts }) {
  const total = counts.up + counts.down;
  if (total === 0) {
    return <p className="subtitle">No ratings yet.</p>;
  }

  // pctDown is 100 - pctUp, not its own rounding, so the two always sum to exactly
  // 100% (and so to the same width split on the bar below) rather than drifting to
  // 99% or 101% from two independent roundings.
  const pctUp = Math.round((counts.up / total) * 100);
  const pctDown = 100 - pctUp;

  return (
    <div className="rating-summary">
      <div className="rating-summary-tiles">
        <div className="rating-summary-tile">
          <span className="rating-summary-dot rating-summary-dot-up" aria-hidden="true" />
          <span className="rating-summary-label">Helpful</span>
          <span className="rating-summary-value">{pctUp}%</span>
          <span className="rating-summary-count">
            {counts.up} rating{counts.up === 1 ? "" : "s"}
          </span>
        </div>
        <div className="rating-summary-tile">
          <span className="rating-summary-dot rating-summary-dot-down" aria-hidden="true" />
          <span className="rating-summary-label">Not helpful</span>
          <span className="rating-summary-value">{pctDown}%</span>
          <span className="rating-summary-count">
            {counts.down} rating{counts.down === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      <div
        className="rating-summary-bar"
        role="img"
        aria-label={`${pctUp}% helpful, ${pctDown}% not helpful, out of ${total} total ratings`}
      >
        {counts.up > 0 && (
          <div
            className="rating-summary-segment rating-summary-segment-up"
            style={{ width: `${pctUp}%` }}
            title={`Helpful: ${counts.up} (${pctUp}%)`}
          >
            {pctUp >= 15 && <span>{pctUp}%</span>}
          </div>
        )}
        {counts.down > 0 && (
          <div
            className="rating-summary-segment rating-summary-segment-down"
            style={{ width: `${pctDown}%` }}
            title={`Not helpful: ${counts.down} (${pctDown}%)`}
          >
            {pctDown >= 15 && <span>{pctDown}%</span>}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Every rating left on a system answer (thumbs up/down, with any comment), independent
 * of whether that question was escalated to an admin — the Student Questions page only
 * shows a rating when it happens to sit on an escalated question, which is the minority.
 * Split into two tabs (Helpful / Not helpful) rather than one blended list, opening on
 * Helpful. `counts` (the unfiltered up/down totals) drives both the tab badges and
 * RatingSummary above them, so neither changes as the active tab is switched.
 */
export default function AdminRatingsPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({ up: 0, down: 0 });
  const [total, setTotal] = useState(0);
  const [ratingFilter, setRatingFilter] = useState(TABS[0].rating);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    adminRatingsApi
      .list({ rating: ratingFilter, page, per_page: PER_PAGE }, token)
      .then((data) => {
        setItems(data.items);
        setCounts(data.counts);
        setTotal(data.total);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [ratingFilter, page, token]);

  // Switching tabs always starts back at page 1, rather than landing on a page number
  // that may not exist in the other tab's result set.
  function changeTab(rating) {
    setRatingFilter(rating);
    setPage(1);
  }

  const lastPage = Math.max(Math.ceil(total / PER_PAGE), 1);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="admin-main">
        <h1>Answer Ratings</h1>

        {/* Loading is gated here too, not just below: without it, the empty {up:0,
            down:0} initial state would flash "No ratings yet" before the real counts
            arrive. */}
        {loading ? <p className="subtitle">Loading...</p> : <RatingSummary counts={counts} />}

        <div className="escalation-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.rating}
              type="button"
              className={`escalation-tab escalation-tab-${tab.rating}${ratingFilter === tab.rating ? " active" : ""}`}
              onClick={() => changeTab(tab.rating)}
            >
              <ThumbIcon down={tab.down} />
              {tab.label}
              {counts[tab.rating] > 0 && <span className="header-badge">{counts[tab.rating]}</span>}
            </button>
          ))}
        </div>

        <Alert>{error}</Alert>

        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : items.length === 0 ? (
          <p className="subtitle">No ratings yet.</p>
        ) : (
          <>
            <div className="escalation-list">
              {items.map((item) => (
                <RatingCard key={item.id} item={item} />
              ))}
            </div>

            {lastPage > 1 && (
              <div className="rating-pagination">
                <Button variant="secondary" onClick={() => setPage((p) => p - 1)} disabled={page <= 1}>
                  Previous
                </Button>
                <span className="subtitle">
                  Page {page} of {lastPage}
                </span>
                <Button variant="secondary" onClick={() => setPage((p) => p + 1)} disabled={page >= lastPage}>
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
