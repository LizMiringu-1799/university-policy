# UPMAN frontend

React (Vite) SPA. Entry point is the Login page (`/`); `/register` is reachable from it; `/dashboard` is a protected placeholder shown after sign-in. See [../docs/design-auth.md](../docs/design-auth.md) §4 for routes, theme tokens, and component structure.

## Setup

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Runs on `http://localhost:5173` and talks to the Flask API at the URL in `.env` (`VITE_API_BASE_URL`, defaults to `http://localhost:5000/api/v1`). Start the backend first — see [../backend/README.md](../backend/README.md).
