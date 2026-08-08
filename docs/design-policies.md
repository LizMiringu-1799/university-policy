# Design — Policy Library & Admin CRUD

Companion to [design-auth.md](design-auth.md) and [implementation-plan.md](implementation-plan.md). Scope: everything that happens after login — students/staff browse, search, and read policies (with an AI-query placeholder); admins get full CRUD over the policy repository. This is objectives 1 and 2 from implementation-plan.md, adapted to MySQL/XAMPP, with the RAG-specific pieces (Chroma, embeddings, indexing) left out — those come later per the roadmap; the AI query surface here is a UI placeholder only.

## 1. The storage question: PDF files on disk, not as DB blobs

**Decision:** the PDF binary lives on the filesystem (`backend/data/pdfs/{document_id}/v{version_number}.pdf`); MySQL stores only metadata and a path pointer.

**Why not store the PDF in MySQL as a BLOB:**
- A `documents` table storing multi-MB binaries bloats every backup, every `mysqldump`, and every replication stream, even though nothing ever queries *inside* the blob.
- Serving a BLOB means Flask has to pull the whole file into memory from the DB before it can respond. Serving a filesystem path lets Flask use `send_file(..., conditional=True)`, which supports HTTP range requests — the browser's PDF viewer fetches only the byte ranges it needs to render the page you're looking at, not the whole file.
- Filesystem storage is trivially inspectable and backed up (copy the directory), where a BLOB requires a DB export to get the file back out.

**Why versioned paths, not overwrite-in-place:** replacing a policy is common (annual review, correction), and for a university policy platform, being able to show what a policy said on a given date is a real requirement, not speculative — so each upload gets its own file (`v1.pdf`, `v2.pdf`, ...) and the old ones are kept. `documents.current_version_id` points at whichever version is "current"; `document_versions` is the append-only history.

**Integrity:** each version stores a `file_sha256` computed on upload, so corruption or a mismatched file is detectable later without re-reading the whole PDF.

This matches the storage approach implementation-plan.md already specified for the full RAG-era design (§3, task 1.4) — no drift, just building the subset needed now without the RAG indexing columns (`index_status`, `chunk_count`, etc.), which stay out until objective 3 actually needs them.

## 2. Database schema

```sql
CREATE TABLE documents (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  title               VARCHAR(200) NOT NULL,
  category            VARCHAR(100) NOT NULL,
  status              ENUM('active','archived') NOT NULL DEFAULT 'active',
  current_version_id  INT NULL,
  created_by          INT NOT NULL,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE document_versions (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  document_id    INT NOT NULL,
  version_number INT NOT NULL,
  file_path      VARCHAR(500) NOT NULL,
  file_sha256    CHAR(64) NOT NULL,
  page_count     INT NULL,
  uploaded_by    INT NOT NULL,
  uploaded_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_doc_version (document_id, version_number),
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (uploaded_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE documents
  ADD CONSTRAINT fk_documents_current_version
  FOREIGN KEY (current_version_id) REFERENCES document_versions(id);
```

**Circular FK, same pattern as `users`/JWT design called out already:** `documents.current_version_id` points at `document_versions`, which points back at `documents`. A document is created in three steps — insert with `current_version_id` NULL, insert version 1, update the document to point at it — same as implementation-plan.md §6 already flagged for this exact pair of tables.

## 3. Roles and permissions

| Action | student | staff | admin |
|---|---|---|---|
| List/search active policies | ✅ | ✅ | ✅ |
| Open/read a policy (current version) | ✅ | ✅ | ✅ |
| Ask AI about a policy (placeholder) | ✅ | ✅ | ✅ |
| Create policy (upload new) | ❌ | ❌ | ✅ |
| Edit metadata (title/category) | ❌ | ❌ | ✅ |
| Replace version (upload new PDF) | ❌ | ❌ | ✅ |
| Archive / restore | ❌ | ❌ | ✅ |

`staff` has no elevated policy permissions here — same "no permissions defined yet" note as design-auth.md; it reads like `student` until a staff-specific module is scoped.

**On "CRUD" — Delete is archive, not a hard delete.** A hard `DELETE` on a policy document is a bad default for an institutional records system: it destroys the audit trail (who published what, when) with no recovery path. "Archive" is the delete operation here — it removes the document from the student/staff library immediately and is fully reversible via "Restore." This matches what implementation-plan.md's admin module already specified (§3, objective 2) before this feature existed, so it's not a new call, just carrying the existing decision forward. Flagging it explicitly since "CRUD" was your wording — say if you actually want a true destructive delete on top of this and I'll add it as a separate, more dangerous action.

## 4. REST API

Base `/api/v1`, same envelope/error shape as design-auth.md.

### Read (any authenticated role)

| Method + path | Params | Returns |
|---|---|---|
| `GET /documents` | `?q=&category=&page=&per_page=` | `{items: [DocumentSummary], total, page, per_page}` — `q` matches title (SQL `LIKE`) |
| `GET /documents/:id` | — | `Document` (includes `versions[]`) |
| `GET /documents/:id/file` | `?version=` (default: current) | PDF bytes, `Content-Disposition: inline`, range-capable |
| `GET /documents/categories` | — | `{categories: [string]}` — distinct values, for the filter dropdown |

Only `status='active'` documents are visible through `GET /documents` and `GET /documents/:id` to non-admins; admins see everything (`?status=archived` to filter).

```json
// DocumentSummary
{ "id": 1, "title": "Examination Policy", "category": "Academic",
  "status": "active", "current_version": 2, "page_count": 14, "updated_at": "2026-08-06T09:00:00Z" }
```

### Admin — `/admin/documents` (role: admin, else `403 forbidden`)

| Method + path | Body | Returns |
|---|---|---|
| `POST /admin/documents` | multipart: `file`, `title`, `category` | `201 Document` |
| `POST /admin/documents/:id/versions` | multipart: `file` | `201 Document` (new current version) |
| `PATCH /admin/documents/:id` | `{title?, category?, status?}` (`status:"archived"` = archive, `"active"` = restore) | `Document` |

Upload validation: `application/pdf` only, 25 MB cap enforced on the stream (matches implementation-plan.md §8.3 — cap before parsing, not after).

## 5. Frontend

### Routes

| Path | Access | Purpose |
|---|---|---|
| `/policies` | any authenticated role | Library: search, category filter, list. **Replaces `/dashboard` as the post-login landing page** — there's no reason to route through an empty placeholder just to click into the real screen. |
| `/policies/:id` | any authenticated role | Reader: PDF view (current version), metadata, "Ask AI" placeholder panel |
| `/admin/policies` | admin only (403-style redirect otherwise) | CRUD table: upload, edit metadata, replace version, archive/restore |

`ProtectedRoute` gains an optional `role` prop for the admin-only route.

### PDF viewing

The browser's native PDF renderer, not a new dependency (`react-pdf`/`pdf.js` add a worker-config dependency that isn't worth it for "open and read"). Flow: `fetch()` the file endpoint with the `Authorization` header (can't put a JWT in an `<iframe src>` URL — that leaks the token into browser history/logs), get a `Blob`, `URL.createObjectURL(blob)`, feed that into an `<iframe>`. Revoke the object URL on unmount.

### AI query placeholder

A panel on the reader page: text input + send button. Submitting shows a static response ("AI Q&A is coming soon — this will answer questions about this policy with cited sources, once the RAG pipeline lands"). No backend call — wiring a fake endpoint now just means throwing it away when objective 3 builds the real one.

## 6. Validation against constraints

- PDFs stored on disk, MySQL holds metadata only — confirmed, §1. ✅
- Student/staff land on the policy library after login, can search → open → read — confirmed, §5. ✅
- AI query is a placeholder, not a real backend call — confirmed, §5. ✅
- Admin gets Create/Read/Update/Archive(-as-Delete) — confirmed, §3–4. ✅
- No drift from implementation-plan.md's existing objective 1/2 design — confirmed, §1–2. ✅
