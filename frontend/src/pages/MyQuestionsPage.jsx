import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { escalationsApi } from "../api/client.js";
import AppHeader from "../components/AppHeader.jsx";
import Alert from "../components/Alert.jsx";
import { formatDate } from "../utils/date.js";

function QuestionCard({ item }) {
  return (
    <div className="escalation-card">
      <div className="escalation-card-header">
        <span className={`status-badge escalation-${item.status}`}>
          {item.status === "open" ? "Waiting on admin" : "Answered"}
        </span>
        <span className="escalation-date">{formatDate(item.created_at)}</span>
      </div>

      <p className="escalation-question">{item.question}</p>

      {item.system_answer_md && (
        <div className="escalation-system-answer">
          <h4>What the system said</h4>
          <p>{item.system_answer_md}</p>
        </div>
      )}

      {item.admin_response ? (
        <div className="escalation-admin-response">
          <h4>Admin's reply</h4>
          <p>{item.admin_response}</p>
        </div>
      ) : (
        <p className="subtitle">An admin hasn't responded yet.</p>
      )}
    </div>
  );
}

export default function MyQuestionsPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    escalationsApi
      .mine(token)
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="admin-main">
        <h1>My Questions</h1>
        <p className="subtitle">Questions sent to an admin, and their replies</p>

        <Alert>{error}</Alert>

        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : items.length === 0 ? (
          <p className="subtitle">You haven't sent any questions to an admin yet.</p>
        ) : (
          <div className="escalation-list">
            {items.map((item) => (
              <QuestionCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
