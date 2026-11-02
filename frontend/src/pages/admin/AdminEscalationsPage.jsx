import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext.jsx";
import { adminEscalationsApi } from "../../api/client.js";
import AppHeader from "../../components/AppHeader.jsx";
import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import { formatDate } from "../../utils/date.js";

// The two kinds of question this queue mixes, kept as separate tabs rather than one
// blended list so an admin can tell at a glance which they're looking at: one the
// system raised on its own (it couldn't answer at all), one a student raised by asking
// for more detail on an answer it did give.
const TABS = [
  { reason: "clarification", label: "Student Raised" },
  { reason: "unanswered", label: "System Raised" },
];

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
 * Admin's queue of student questions handed off from the RAG assistant, split into two
 * tabs: questions a student raised themselves (via "Request clarification" on an answer
 * they got) and questions the system raised on its own (it couldn't answer at all).
 * Opens on the student-raised tab. Within a tab, defaults to the "open" status filter,
 * since that's the actionable work; "resolved" and "All" are there for reference. Each
 * tab's open count is its own badge; the header nav badge (AppHeader) is the sum of both.
 */
export default function AdminEscalationsPage() {
  const { token } = useAuth();
  const [reasonFilter, setReasonFilter] = useState(TABS[0].reason);
  const [items, setItems] = useState([]);
  const [statusFilter, setStatusFilter] = useState("open");
  const [openCounts, setOpenCounts] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    adminEscalationsApi
      .list({ status: statusFilter, reason: reasonFilter }, token)
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, [statusFilter, reasonFilter, token]);

  // Tab badges: each tab's own open count, refreshed alongside the list so resolving a
  // question updates the count it just came out of without a manual reload.
  useEffect(() => {
    Promise.all(TABS.map((tab) => adminEscalationsApi.openCount(token, { reason: tab.reason })))
      .then((results) => {
        const next = {};
        TABS.forEach((tab, i) => {
          next[tab.reason] = results[i].count;
        });
        setOpenCounts(next);
      })
      .catch(() => {});
  }, [token, items]);

  // Switching tabs always starts back at the default status filter, so a resolved-only
  // filter left on from the other tab doesn't quietly hide everything here too.
  function changeTab(reason) {
    setReasonFilter(reason);
    setStatusFilter("open");
  }

  return (
    <div className="app-page">
      <AppHeader />
      <main className="admin-main">
        <h1>Student Questions</h1>

        <div className="escalation-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.reason}
              type="button"
              className={`escalation-tab${reasonFilter === tab.reason ? " active" : ""}`}
              onClick={() => changeTab(tab.reason)}
            >
              {tab.label}
              {openCounts[tab.reason] > 0 && <span className="header-badge">{openCounts[tab.reason]}</span>}
            </button>
          ))}
        </div>

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
