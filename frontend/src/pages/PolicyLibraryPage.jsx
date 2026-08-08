import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { documentsApi } from "../api/client.js";
import { formatDate } from "../utils/date.js";
import AppHeader from "../components/AppHeader.jsx";
import Alert from "../components/Alert.jsx";
import AiQueryPanel from "../components/AiQueryPanel.jsx";

export default function PolicyLibraryPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    documentsApi.categories(token).then((data) => setCategories(data.categories)).catch(() => {});
  }, [token]);

  useEffect(() => {
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      documentsApi
        .list({ q, category }, token)
        .then((data) => setItems(data.items))
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [q, category, token]);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="library-main">
        <h1>Policy Library</h1>
        <p className="subtitle">Search and browse university policies</p>

        <AiQueryPanel
          as="section"
          className="ai-panel-inline"
          fieldId="library-ai-question"
          title="Not sure which policy covers this?"
          placeholder="e.g. Can I defer an exam if I'm sick?"
        />

        <div className="library-filters">
          <input
            type="search"
            placeholder="Search policies by title..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="library-search"
          />
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="library-category">
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <Alert>{error}</Alert>

        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : items.length === 0 ? (
          <p className="subtitle">No policies match your search.</p>
        ) : (
          <ul className="policy-list">
            {items.map((doc) => (
              <li key={doc.id}>
                <Link to={`/policies/${doc.id}`} className="policy-card">
                  <div className="policy-card-main">
                    <h3>{doc.title}</h3>
                    <span className="category-badge">{doc.category}</span>
                  </div>
                  <div className="policy-card-meta">
                    {doc.page_count != null && <span>{doc.page_count} pages</span>}
                    <span>v{doc.current_version}</span>
                    <span>Updated {formatDate(doc.updated_at)}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
