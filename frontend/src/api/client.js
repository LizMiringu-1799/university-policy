// Thin REST client for the Flask API. Every exported *Api object below is a 1:1 mapping
// onto one backend blueprint (see backend/app/routes/*.py); this file adds no business
// logic of its own, just request plumbing and JSON-error handling shared across them.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5001/api/v1";

/**
 * Core fetch wrapper: attaches the bearer token, JSON-encodes `body` (or passes a
 * FormData body through untouched, for file uploads), and throws an Error carrying the
 * backend's `error.message` on a non-2xx response so callers can just .catch(err => ...).
 */
async function request(path, { method = "GET", body, token } = {}) {
  const isFormData = body instanceof FormData;
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!isFormData && body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const message = data?.error?.message || "something went wrong";
    throw new Error(message);
  }

  return data;
}

/** Like request(), but for a binary response (the PDF file) instead of JSON. */
async function requestBlob(path, { token } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { headers });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.error?.message || "failed to load file");
  }
  return res.blob();
}

/** Build a "?a=1&b=2" query string, dropping any param that's undefined/null/"". */
function toQueryString(params = {}) {
  const usable = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (usable.length === 0) return "";
  return `?${new URLSearchParams(usable).toString()}`;
}

// Session: register/login return {user, access_token}; me() resolves a stored token
// back to a user on app load. Maps to routes/auth.py.
export const authApi = {
  register: (payload) => request("/auth/register", { method: "POST", body: payload }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload }),
  me: (token) => request("/auth/me", { token }),
};

// Read-only policy browsing (library, reader, categories filter) plus the raw PDF blob.
// Archived documents are invisible here unless the caller is an admin (enforced
// server-side). Maps to routes/documents.py.
export const documentsApi = {
  list: (params, token) => request(`/documents${toQueryString(params)}`, { token }),
  categories: (token) => request("/documents/categories", { token }),
  detail: (id, token) => request(`/documents/${id}`, { token }),
  fileBlob: (id, token, version) => requestBlob(`/documents/${id}/file${toQueryString({ version })}`, { token }),
  // Extracted, paginated text for formats the browser can't render natively (Word docs,
  // plain text/markdown) — see document.viewer ("pdf" | "image" | "text").
  text: (id, token, version) => request(`/documents/${id}/text${toQueryString({ version })}`, { token }),
};

// The RAG "ask a question" endpoint and the rating on its answers. Maps to routes/queries.py.
export const queriesApi = {
  // documentId scopes the search to one policy; omit it to search the whole corpus.
  // sessionId is a client-generated id per chat panel, logged so analytics can group
  // one user's rephrasings of the same question.
  ask: (question, token, documentId, sessionId) =>
    request("/ask", {
      method: "POST",
      body: { question, document_id: documentId, session_id: sessionId },
      token,
    }),
  // The requesting user's own chat history: every question they've asked the AI
  // assistant, however it turned out. Distinct from escalationsApi.mine, which is only
  // the subset handed off to an admin.
  mine: (params, token) => request(`/queries/mine${toQueryString(params)}`, { token }),
  // Thumbs up/down on the answer with the given log_id. Posting again replaces the
  // earlier rating; leave `comment` out of the payload to keep a comment already sent.
  feedback: (logId, payload, token) =>
    request(`/queries/${logId}/feedback`, { method: "POST", body: payload, token }),
};

// Student side of the human-escalation feature: hand a question to an admin, and check
// back for their reply. Maps to routes/escalations.py.
export const escalationsApi = {
  create: (payload, token) => request("/escalations", { method: "POST", body: payload, token }),
  mine: (token) => request("/escalations/mine", { token }),
};

// Admin side of the same feature: work the queue and reply. Maps to routes/admin_escalations.py.
export const adminEscalationsApi = {
  // `params` supports both `status` (open|resolved) and `reason` (unanswered|clarification),
  // the latter separating the queue into student-raised vs system-raised questions.
  list: (params, token) => request(`/admin/escalations${toQueryString(params)}`, { token }),
  // `params.reason` scopes the count to one of the two queues; omitted, it's the
  // aggregate the header nav badge shows.
  openCount: (token, params) => request(`/admin/escalations/open-count${toQueryString(params)}`, { token }),
  respond: (id, adminResponse, token) =>
    request(`/admin/escalations/${id}/respond`, { method: "POST", body: { admin_response: adminResponse }, token }),
};

// Every student/staff rating on a system answer, independent of escalation status.
// Maps to routes/admin_ratings.py.
export const adminRatingsApi = {
  list: (params, token) => request(`/admin/ratings${toQueryString(params)}`, { token }),
};

// Read-only reporting on data objective 3 already logs (objective 5). Maps to
// routes/admin_analytics.py.
export const adminAnalyticsApi = {
  // `params.from`/`params.to` (YYYY-MM-DD) scope the window; omitted, it's all history.
  summary: (params, token) => request(`/admin/analytics/summary${toQueryString(params)}`, { token }),
  // Every document that has ever been retrieved, most-retrieved first. No params.
  documents: (token) => request("/admin/analytics/documents", { token }),
  // Documents retrieved often but cited rarely, most-ignored first. `params.limit`.
  ambiguous: (params, token) => request(`/admin/analytics/ambiguous${toQueryString(params)}`, { token }),
};

// Document lifecycle management: upload, replace a version, edit/archive/restore, and
// the ingestion-status polling the admin table uses. Maps to routes/admin_documents.py.
export const adminDocumentsApi = {
  create: (formData, token) => request("/admin/documents", { method: "POST", body: formData, token }),
  addVersion: (id, formData, token) =>
    request(`/admin/documents/${id}/versions`, { method: "POST", body: formData, token }),
  update: (id, payload, token) => request(`/admin/documents/${id}`, { method: "PATCH", body: payload, token }),
  indexStatus: (id, token) => request(`/admin/documents/${id}/index-status`, { token }),
  reindex: (id, token) => request(`/admin/documents/${id}/reindex`, { method: "POST", token }),
};
