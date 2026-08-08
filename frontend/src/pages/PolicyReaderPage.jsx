import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { documentsApi } from "../api/client.js";
import { formatDate } from "../utils/date.js";
import AppHeader from "../components/AppHeader.jsx";
import Alert from "../components/Alert.jsx";
import AiQueryPanel from "../components/AiQueryPanel.jsx";

export default function PolicyReaderPage() {
  const { id } = useParams();
  const { token } = useAuth();
  const [document_, setDocument] = useState(null);
  const [fileUrl, setFileUrl] = useState(null);
  const [error, setError] = useState("");
  const objectUrlRef = useRef(null);

  useEffect(() => {
    documentsApi
      .detail(id, token)
      .then(setDocument)
      .catch((err) => setError(err.message));
  }, [id, token]);

  useEffect(() => {
    let cancelled = false;
    documentsApi
      .fileBlob(id, token)
      .then((blob) => {
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        setFileUrl(url);
      })
      .catch((err) => setError(err.message));

    return () => {
      cancelled = true;
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, [id, token]);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="reader-main">
        <Link to="/policies" className="back-link">
          ← Back to library
        </Link>

        <Alert>{error}</Alert>

        {document_ && (
          <div className="reader-heading">
            <h1>{document_.title}</h1>
            <div className="policy-card-meta">
              <span className="category-badge">{document_.category}</span>
              <span>v{document_.current_version}</span>
              {document_.page_count != null && <span>{document_.page_count} pages</span>}
              <span>Updated {formatDate(document_.updated_at)}</span>
            </div>
          </div>
        )}

        <div className="reader-layout">
          <div className="reader-viewer">
            {fileUrl ? (
              <iframe src={fileUrl} title="Policy document" className="reader-iframe" />
            ) : (
              !error && <p className="subtitle">Loading document...</p>
            )}
          </div>

          <AiQueryPanel
            as="aside"
            className="ai-panel"
            fieldId="ai-question"
            title="Ask AI about this policy"
            placeholder="e.g. What's the late submission penalty?"
            documentId={Number(id)}
          />
        </div>
      </main>
    </div>
  );
}
