const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api/v1";

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

function toQueryString(params = {}) {
  const usable = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (usable.length === 0) return "";
  return `?${new URLSearchParams(usable).toString()}`;
}

export const authApi = {
  register: (payload) => request("/auth/register", { method: "POST", body: payload }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload }),
  me: (token) => request("/auth/me", { token }),
};

export const documentsApi = {
  list: (params, token) => request(`/documents${toQueryString(params)}`, { token }),
  categories: (token) => request("/documents/categories", { token }),
  detail: (id, token) => request(`/documents/${id}`, { token }),
  fileBlob: (id, token, version) => requestBlob(`/documents/${id}/file${toQueryString({ version })}`, { token }),
};

export const queriesApi = {
  // documentId scopes the search to one policy; omit it to search the whole corpus.
  ask: (question, token, documentId) =>
    request("/ask", { method: "POST", body: { question, document_id: documentId }, token }),
};

export const adminDocumentsApi = {
  create: (formData, token) => request("/admin/documents", { method: "POST", body: formData, token }),
  addVersion: (id, formData, token) =>
    request(`/admin/documents/${id}/versions`, { method: "POST", body: formData, token }),
  update: (id, payload, token) => request(`/admin/documents/${id}`, { method: "PATCH", body: payload, token }),
  indexStatus: (id, token) => request(`/admin/documents/${id}/index-status`, { token }),
  reindex: (id, token) => request(`/admin/documents/${id}/reindex`, { method: "POST", token }),
};
