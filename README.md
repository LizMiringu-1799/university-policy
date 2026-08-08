# university-policy

an intelligent platform for centralizing fragmented institutional docs/policies

## Structure

- [backend/](backend/) — Flask REST API (MySQL via XAMPP): auth, the policy repository, and the RAG pipeline (local embeddings + Chroma, grounded answers with citations)
- [frontend/](frontend/) — React (Vite) SPA, entry point is the Login page
- [docs/](docs/) — objectives, full implementation plan, and per-module designs (auth, policy library, RAG)

## Getting started

1. [backend/README.md](backend/README.md) — start MySQL in XAMPP, set up the Flask API (venv + `.env` + migrations)
2. [frontend/README.md](frontend/README.md) — install frontend deps, set up `.env`
3. From the repo root: `npm install`, then `npm run dev` — starts the Flask API and the Vite dev server together (via `concurrently`)

The "Ask AI" panels need an `LLM_API_KEY` in `backend/.env`; see [backend/README.md](backend/README.md) §8. Everything else, including policy search, runs with no external service and no cost.
