import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { documentsApi } from "../api/client.js";
import { formatDate } from "../utils/date.js";
import AppHeader from "../components/AppHeader.jsx";
import Alert from "../components/Alert.jsx";
import AiQueryPanel from "../components/AiQueryPanel.jsx";

/** PDF/image viewer: fetches the file as a blob (so the request carries the auth token)
 * and shows it in whatever the browser renders natively for that media type. `page`
 * deep-links a PDF via the #page= hash; images are always a single page. */
function FileViewer({ id, token, page, viewer, setError }) {
  const [fileUrl, setFileUrl] = useState(null);
  const objectUrlRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setFileUrl(null);
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

  if (!fileUrl) return <p className="subtitle">Loading document...</p>;

  if (viewer === "image") {
    return <img src={fileUrl} alt="Policy document" className="reader-image" />;
  }

  return (
    // Keyed on the full src (page included) so a citation jump to a page already
    // "loaded" still re-navigates the embedded PDF viewer instead of being a no-op
    // hash change the plugin ignores.
    <iframe
      key={page ? `${fileUrl}#page=${page}` : fileUrl}
      src={page ? `${fileUrl}#page=${page}` : fileUrl}
      title="Policy document"
      className="reader-iframe"
    />
  );
}

/** Viewer for formats the browser can't render natively (Word docs, plain text/markdown):
 * the extracted text, paginated the same way indexing and citations see it. `page` scrolls
 * to and highlights the matching pseudo-page, standing in for the PDF viewer's #page=N. */
function TextViewer({ id, token, page, setError }) {
  const [pages, setPages] = useState(null);

  useEffect(() => {
    setPages(null);
    documentsApi
      .text(id, token)
      .then((data) => setPages(data.pages))
      .catch((err) => setError(err.message));
  }, [id, token]);

  useEffect(() => {
    if (!pages || !page) return;
    document.getElementById(`policy-page-${page}`)?.scrollIntoView({ block: "start" });
  }, [pages, page]);

  if (!pages) return <p className="subtitle">Loading document...</p>;

  return (
    <div className="reader-text">
      {pages.map((p) => (
        <section
          key={p.page}
          id={`policy-page-${p.page}`}
          className={`reader-text-page${String(p.page) === page ? " reader-text-page-highlighted" : ""}`}
        >
          <span className="reader-text-page-number">Page {p.page}</span>
          <p>{p.text}</p>
        </section>
      ))}
    </div>
  );
}

/**
 * Single-policy view: the document itself alongside an AiQueryPanel scoped to just this
 * document. Citation links (?page=N) work the same way across formats — a PDF page jump,
 * for Word/text a scroll to the matching pseudo-page — but which viewer renders at all
 * depends on `document_.viewer` ("pdf" | "image" | "text"), set by the backend from the
 * current version's file type.
 */
export default function PolicyReaderPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const page = searchParams.get("page");
  const { token } = useAuth();
  const [document_, setDocument] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    documentsApi
      .detail(id, token)
      .then(setDocument)
      .catch((err) => setError(err.message));
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
            {document_ &&
              (document_.viewer === "text" ? (
                <TextViewer id={id} token={token} page={page} setError={setError} />
              ) : (
                <FileViewer id={id} token={token} page={page} viewer={document_.viewer} setError={setError} />
              ))}
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
