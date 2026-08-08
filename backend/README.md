# UPMAN backend

Flask REST API: auth, the policy repository and admin CRUD, and the full RAG pipeline (Chroma indexing, retrieval, and grounded answers with citations). Designs: [design-auth.md](../docs/design-auth.md), [design-policies.md](../docs/design-policies.md), [design-rag.md](../docs/design-rag.md). Full platform plan: [implementation-plan.md](../docs/implementation-plan.md).

## 1. Start MySQL via XAMPP

1. Open the XAMPP Control Panel and click **Start** next to **MySQL** (Apache isn't required — Flask runs its own server).
2. Open [http://localhost/phpmyadmin](http://localhost/phpmyadmin), click **New**, create a database named `upman_db` with collation `utf8mb4_general_ci`.

   Or via the MySQL shell (`C:\xampp\mysql\bin\mysql.exe -u root`):

   ```sql
   CREATE DATABASE upman_db CHARACTER SET utf8mb4;
   ```

## 2. Set up the Python environment

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

XAMPP's default MySQL has user `root` with no password — `.env.example` already matches that. Edit `.env` if your setup differs.

## 3. Create the schema

Migrations are already in the repo, so this just applies them:

```powershell
$env:FLASK_APP = "run.py"
flask db upgrade
```

Only run `flask db migrate` when you have changed a model and need a new migration.

## 4. Seed an admin account

Self-registration always creates `student` accounts (see design-auth.md §1). Create the first admin via:

```powershell
flask seed-admin
```

## 5. (Optional) Demo accounts

```powershell
flask seed-demo
```

Creates three fixed demo accounts — student, admin, staff — all with password `Pass@123`:

| Email | Role |
|---|---|
| `student@dkut.ac.ke` | student |
| `admin@dkut.ac.ke` | admin |
| `staff@dkut.ac.ke` | staff |

Safe to re-run — skips any account that already exists.

## 6. Run the API

```powershell
python run.py
```

Runs on `http://localhost:5000`, with endpoints under `/api/v1`. Contracts: design-auth.md §3 for auth, design-policies.md §4 for documents and admin CRUD, design-rag.md §7 for the index endpoints.

## 7. Policy indexing (RAG)

Uploading a policy queues it for indexing on a background worker: text extraction, chunking, embedding, then storage in a local Chroma index under `data/chroma`. The admin table's **Index** column shows `pending` to `indexing` to `indexed`, refreshing on its own while work is in flight.

**The first indexing run downloads an ~80 MB embedding model** and will take a minute. After that it is cached and offline.

The index tracks the current version of every active document, and nothing else. Replacing a version drops the old version's chunks once the new ones are stored, and archiving removes the document from the index entirely.

Documents that fail to index show `failed` with a **Why?** link giving the reason. The usual cause is a PDF with no text layer, either a scan (OCR is out of scope) or a blank file.

| Command | What it does |
|---|---|
| `flask reindex` | Rebuild the index for every active document |
| `flask reindex --document-id 3` | Rebuild one document |
| `flask search "late submission penalty"` | Print the top matching chunks with similarity scores |

`flask search` is how you sanity-check retrieval quality without the chat UI. **Stop the API before running `flask reindex`**: Chroma expects a single process against its data directory, and two writers corrupt the index rather than erroring.

## 8. Answering (the "Ask AI" panels)

`POST /api/v1/ask` takes `{question, document_id?}` and returns a grounded answer with citations. It retrieves the top-k chunks, sends them to the model as numbered extracts in a single call, and parses the inline `[n]` markers back into citation objects. Pass `document_id` to scope the search to one policy, which is what the reader page's panel does; omit it to search the whole corpus.

**Set `LLM_API_KEY` in `.env` or the panels return a 502.** The default provider is [Groq](https://console.groq.com), whose free tier needs no credit card:

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=gsk_...
```

Any OpenAI-compatible endpoint works, so switching provider is these three values and a restart. Gemini, Cerebras, OpenRouter, a local Ollama at `http://localhost:11434/v1`, and Anthropic's compatibility layer all fit.

Two behaviours worth recognising:

- **`answered: false`** means the indexed policies don't cover the question, or it wasn't about policy. The answer text says which. This is the intended path, not a failure, and it's the signal objective 4 mines for policy gaps.
- **429 `rate_limited`** means the free tier's per-minute ceiling was hit. Expected under concurrent use rather than a fault; the panel invites a retry.

Costs nothing per query: embeddings are local and the model is on a free tier. See [design-rag.md](../docs/design-rag.md) §9 for why it's a single call rather than an agent loop, and why citations are parsed from the text rather than requested as a field.
