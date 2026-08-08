import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext.jsx";
import { documentsApi, adminDocumentsApi } from "../../api/client.js";
import AppHeader from "../../components/AppHeader.jsx";
import Alert from "../../components/Alert.jsx";
import Button from "../../components/Button.jsx";
import TextField from "../../components/TextField.jsx";

function UploadForm({ onCreated }) {
  const { token } = useAuth();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) {
      setError("choose a PDF file");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("category", category);
      formData.append("file", file);
      await adminDocumentsApi.create(formData, token);
      setTitle("");
      setCategory("");
      setFile(null);
      e.target.reset();
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <h2>Add a policy</h2>
      <Alert>{error}</Alert>
      <div className="upload-form-row">
        <TextField id="new-title" label="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <TextField
          id="new-category"
          label="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          required
        />
        <div className="field">
          <label htmlFor="new-file">PDF file</label>
          <input
            id="new-file"
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />
        </div>
      </div>
      <Button type="submit" disabled={submitting}>
        {submitting ? "Uploading..." : "Upload policy"}
      </Button>
    </form>
  );
}

function IndexCell({ doc, indexError, onExplain }) {
  if (!doc.index_status) return <span className="index-chunks">no version</span>;
  // Archiving deletes the chunks but leaves index_status recording the last attempt, so
  // reading it straight would claim an archived policy is still searchable.
  if (doc.status === "archived") return <span className="index-chunks">not indexed</span>;

  return (
    <div className="index-cell">
      <span className={`status-badge index-${doc.index_status}`}>{doc.index_status}</span>
      {doc.index_status === "indexed" && <span className="index-chunks">{doc.chunk_count} chunks</span>}
      {doc.index_status === "failed" &&
        (indexError ? (
          <span className="index-error">{indexError}</span>
        ) : (
          <button type="button" className="index-why" onClick={onExplain}>
            Why?
          </button>
        ))}
    </div>
  );
}

function AdminPolicyRow({ doc, onChanged }) {
  const { token } = useAuth();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(doc.title);
  const [category, setCategory] = useState(doc.category);
  const [error, setError] = useState("");
  const [indexError, setIndexError] = useState("");
  const [busy, setBusy] = useState(false);

  async function saveMetadata() {
    setError("");
    setBusy(true);
    try {
      await adminDocumentsApi.update(doc.id, { title, category }, token);
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleArchive() {
    setError("");
    setBusy(true);
    try {
      await adminDocumentsApi.update(doc.id, { status: doc.status === "active" ? "archived" : "active" }, token);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function explainIndexFailure() {
    try {
      const status = await adminDocumentsApi.indexStatus(doc.id, token);
      setIndexError(status.index_error || "no detail recorded");
    } catch (err) {
      setIndexError(err.message);
    }
  }

  async function reindex() {
    setError("");
    setIndexError("");
    setBusy(true);
    try {
      await adminDocumentsApi.reindex(doc.id, token);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function replaceVersion(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await adminDocumentsApi.addVersion(doc.id, formData, token);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  return (
    <tr>
      <td>
        {editing ? (
          <input value={title} onChange={(e) => setTitle(e.target.value)} className="inline-input" />
        ) : (
          doc.title
        )}
      </td>
      <td>
        {editing ? (
          <input value={category} onChange={(e) => setCategory(e.target.value)} className="inline-input" />
        ) : (
          doc.category
        )}
      </td>
      <td>
        <span className={`status-badge status-${doc.status}`}>{doc.status}</span>
      </td>
      <td>v{doc.current_version}</td>
      <td>
        <IndexCell doc={doc} indexError={indexError} onExplain={explainIndexFailure} />
      </td>
      <td className="admin-actions">
        {error && <span className="field-error">{error}</span>}
        {editing ? (
          <>
            <Button variant="secondary" onClick={saveMetadata} disabled={busy}>
              Save
            </Button>
            <Button variant="secondary" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={() => setEditing(true)} disabled={busy}>
              Edit
            </Button>
            <label className="btn btn-secondary file-btn">
              Replace file
              <input type="file" accept="application/pdf" onChange={replaceVersion} hidden />
            </label>
            {doc.status === "active" && (
              <Button variant="secondary" onClick={reindex} disabled={busy}>
                Reindex
              </Button>
            )}
            <Button variant="secondary" onClick={toggleArchive} disabled={busy}>
              {doc.status === "active" ? "Archive" : "Restore"}
            </Button>
          </>
        )}
      </td>
    </tr>
  );
}

export default function AdminPoliciesPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // `silent` keeps the poll from swapping the table for "Loading..." every few seconds,
  // which would also throw away whatever an admin is part-way through typing in a row.
  function refresh({ silent = false } = {}) {
    if (!silent) setLoading(true);
    documentsApi
      .list({ status: statusFilter }, token)
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message))
      .finally(() => {
        if (!silent) setLoading(false);
      });
  }

  useEffect(refresh, [statusFilter, token]);

  // Indexing runs on a background worker, so the row that says "pending" now says
  // "indexed" a few seconds later without the admin touching anything. Only active
  // documents are watched: archiving a pending one leaves it pending forever, and
  // polling on that would never stop.
  useEffect(() => {
    const indexing = items.some(
      (doc) => doc.status === "active" && (doc.index_status === "pending" || doc.index_status === "indexing")
    );
    if (!indexing) return undefined;
    const timer = setTimeout(() => refresh({ silent: true }), 3000);
    return () => clearTimeout(timer);
  }, [items]);

  return (
    <div className="app-page">
      <AppHeader />
      <main className="admin-main">
        <h1>Manage Policies</h1>
        <p className="subtitle">Upload, edit, replace versions, and archive policy documents</p>

        <UploadForm onCreated={refresh} />

        <div className="admin-table-header">
          <h2>All policies</h2>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="library-category">
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </div>

        <Alert>{error}</Alert>

        {loading ? (
          <p className="subtitle">Loading...</p>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Category</th>
                <th>Status</th>
                <th>Version</th>
                <th>Index</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <AdminPolicyRow key={doc.id} doc={doc} onChanged={refresh} />
              ))}
            </tbody>
          </table>
        )}
      </main>
    </div>
  );
}
