import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { documentsApi } from "../api/client.js";
import Button from "../components/Button.jsx";
import Alert from "../components/Alert.jsx";

const STEPS = [
  {
    title: "Browse the library",
    body: "Search by title or filter by category to find the policy you need, then open it to read the full document.",
  },
  {
    title: "Ask a question",
    body: "Type a question in plain language. The system searches the policies and answers with links to the exact pages it used.",
  },
  {
    title: "Rate the answer",
    body: "Use the thumbs up or down on an answer so admins can see which policies are clear and which need work.",
  },
  {
    title: "Ask an admin",
    body: "If the system can't answer, or you want a person to confirm, send the question to an admin. Their reply appears under My Questions.",
  },
];

/**
 * Post-login landing page: a short how-to, the list of policies currently in the system
 * (fetched live so it never goes stale), and a button into the policy library. Both
 * LoginPage and RegisterPage navigate here after a successful session is created.
 */
export default function WelcomePage() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    documentsApi
      .list({}, token)
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="app-page">
      <main className="welcome-main">
        <div className="brand-mark">UPMAN</div>
        <h1>Welcome{user?.name ? `, ${user.name}` : ""}</h1>
        <p className="subtitle">
          UPMAN lets you read university policies and get answers to your questions about them.
        </p>

        <h2 className="welcome-heading">How to use the system</h2>
        <ol className="welcome-steps">
          {STEPS.map((step, i) => (
            <li key={step.title} className="welcome-step">
              <span className="welcome-step-num">{i + 1}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <h2 className="welcome-heading">Policies currently available</h2>
        <Alert>{error}</Alert>
        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : items.length === 0 && !error ? (
          <p className="subtitle">No policies have been added yet.</p>
        ) : (
          <ul className="welcome-policies">
            {items.map((doc) => (
              <li key={doc.id}>
                <span>{doc.title}</span>
                <span className="category-badge">{doc.category}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="welcome-cta">
          <Button onClick={() => navigate("/policies")}>Go to the policy library</Button>
        </div>
      </main>
    </div>
  );
}
