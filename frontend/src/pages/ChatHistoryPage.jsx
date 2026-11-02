import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { queriesApi } from "../api/client.js";
import AppHeader from "../components/AppHeader.jsx";
import Alert from "../components/Alert.jsx";
import AnswerBody from "../components/AnswerBody.jsx";
import AnswerRating from "../components/AnswerRating.jsx";
import Button from "../components/Button.jsx";
import { formatDate } from "../utils/date.js";

const PER_PAGE = 20;

/** One past exchange with the AI assistant. Citation markers in the answer render as
 * plain superscripts rather than clickable source links: unlike a fresh answer from
 * AiQueryPanel, chat history doesn't have the per-citation page numbers to link to
 * (queries.py — those live in query_retrievals, which doesn't exist yet). */
function HistoryCard({ item }) {
  return (
    <div className="escalation-card">
      <div className="escalation-card-header">
        <span className="escalation-date">{formatDate(item.created_at)}</span>
        {item.document && (
          <Link to={`/policies/${item.document.id}`} className="rating-document-link">
            {item.document.title}
          </Link>
        )}
      </div>

      <p className="escalation-question">{item.question}</p>

      {item.status === "error" ? (
        <p className="subtitle">This didn't get a response — try asking again.</p>
      ) : (
        <>
          <div className="ai-answer-body">
            <AnswerBody text={item.answer_md} />
          </div>
          <div className="ai-answer-meta">
            {item.status === "answered" ? (
              <span className="ai-confidence">confidence {Math.round(item.confidence * 100)}%</span>
            ) : (
              <span className="ai-unanswered">not covered by the indexed policies</span>
            )}
          </div>
          <AnswerRating
            key={item.id}
            logId={item.id}
            initialRating={item.rating?.rating ?? null}
            initialComment={item.rating?.comment ?? ""}
          />
        </>
      )}
    </div>
  );
}

/**
 * Every question the current user has put to the AI assistant, however it turned out —
 * answered, unanswered, or a provider hiccup — newest first. Distinct from My Questions
 * (MyQuestionsPage), which is only the subset handed off to an admin; this is everything,
 * including exchanges the AI resolved on its own, so a student can find something they
 * asked before without needing to have escalated it.
 */
export default function ChatHistoryPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    queriesApi
      .mine({ page, per_page: PER_PAGE }, token)
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [page, token]);

  const lastPage = Math.max(Math.ceil(total / PER_PAGE), 1);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="admin-main">
        <h1>Chat History</h1>

        <Alert>{error}</Alert>

        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : items.length === 0 ? (
          <p className="subtitle">You haven't asked the AI assistant anything yet.</p>
        ) : (
          <>
            <div className="escalation-list">
              {items.map((item) => (
                <HistoryCard key={item.id} item={item} />
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
