import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext.jsx";
import { adminEscalationsApi } from "../../api/client.js";
import AppHeader from "../../components/AppHeader.jsx";
import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import { formatDate } from "../../utils/date.js";

/**
 * One student question, with the full context an admin needs to answer it: who asked,
 * from which policy's reader page (if any), what the RAG system already told them, and
 * a reply box that resolves the escalation on submit. `onResolved` re-runs the parent's
 * fetch so a just-answered row moves out of the open queue immediately.
 */
function EscalationRow({ item, onResolved }) {
  const { token } = useAuth();
  const [response, setResponse] = useState(item.admin_response || "");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!response.trim()) {
      setError("write a reply before sending");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await adminEscalationsApi.respond(item.id, response.trim(), token);
      onResolved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="escalation-card">
      <div className="escalation-card-header">
        <span className={`status-badge escalation-${item.status}`}>{item.status}</span>
        <span className="escalation-date">{formatDate(item.created_at)}</span>
        <span className="escalation-reason">{item.reason === "unanswered" ? "not covered by policies" : "clarification requested"}</span>
      </div>

      <p className="escalation-meta">
        {item.student?.name || "Unknown student"}
        {item.document ? ` — ${item.document.title}` : ""}
      </p>

      <p className="escalation-question">{item.question}</p>

      {item.system_answer_md && (
        <div className="escalation-system-answer">
          <h4>What the system told them</h4>
          <p>{item.system_answer_md}</p>
          {item.system_confidence != null && (
            <span className="ai-confidence">confidence {Math.round(item.system_confidence * 100)}%</span>
          )}
        </div>
      )}

      {item.status === "resolved" ? (
        <div className="escalation-admin-response">
          <h4>Your reply</h4>
          <p>{item.admin_response}</p>
        </div>
      ) : (
        <div className="escalation-reply-form">
          <textarea
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Write a reply for the student..."
            rows={3}
            disabled={submitting}
          />
          {error && <span className="field-error">{error}</span>}
          <Button onClick={submit} disabled={submitting}>
            {submitting ? "Sending..." : "Send reply"}
          </Button>
        </div>
      )}
    </div>
  );
}

/**
 * Admin's queue of student questions handed off from the RAG assistant. Defaults to
 * the "open" filter, since that's the actionable work; "resolved" and "All" are there
 * for reference. This is also what the header badge count (AppHeader) is counting.
 */
export default function AdminEscalationsPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [statusFilter, setStatusFilter] = useState("open");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    adminEscalationsApi
      .list({ status: statusFilter }, token)
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, [statusFilter, token]);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="admin-main">
        <h1>Student Questions</h1>
        <p className="subtitle">Questions the assistant couldn't answer, or where a student wants more detail</p>

        <div className="admin-table-header">
          <h2>Questions</h2>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="library-category">
            <option value="open">Waiting on a reply</option>
            <option value="resolved">Answered</option>
            <option value="">All</option>
          </select>
        </div>

        <Alert>{error}</Alert>

        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : items.length === 0 ? (
          <p className="subtitle">Nothing here.</p>
        ) : (
          <div className="escalation-list">
            {items.map((item) => (
              <EscalationRow key={item.id} item={item} onResolved={refresh} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
