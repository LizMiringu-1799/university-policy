# Design — Registration & Login Module

Companion to [implementation-plan.md](implementation-plan.md). Scope: auth only — register, login, `me` — as the first vertical slice of UPMAN. Supersedes the SQLite decision in implementation-plan.md §1 (see update there).

## 1. Decisions (this slice)

| Decision | Choice |
|---|---|
| Backend | Flask (Python), same as implementation-plan.md |
| Relational DB | MySQL, served by XAMPP (Apache/MySQL/phpMyAdmin stack), replacing SQLite |
| DB driver | PyMySQL (pure Python, no native build step — easier on Windows than mysqlclient) |
| Frontend | React (Vite), same as implementation-plan.md |
| Auth | JWT (flask-jwt-extended), stateless access token only — no refresh token, no OTP, no email/SMS verification |
| Password storage | bcrypt hash (flask-bcrypt) |
| Entry point | `/` renders the Login page. `/register` is a secondary route reached via a link on Login. |
| Self-registration role | Always `student`. `admin` and `staff` accounts are seeded via a Flask CLI command, not through the public register endpoint (matches implementation-plan.md task 1.3) |
| Roles | `student`, `admin`, `staff` (`staff` added 2026-08-06 for demo data; no staff-specific permissions exist yet — treated like `student` until a staff module is designed) |
| Color theme | White base, green primary, yellow/orange accent (palette in §4) |

**Why no refresh token:** the brief asks for JWT without OTP/SMS — it doesn't ask for session renewal. A single access token with a practical expiry (24h) keeps the surface area to three endpoints and no token-revocation table. If session length becomes a problem later, a refresh-token table is an additive change, not a rework.

## 2. Database schema

```sql
CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(120) NOT NULL,
  email         VARCHAR(190) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('student','admin','staff') NOT NULL DEFAULT 'student',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at DATETIME NULL,
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Matches `users` in implementation-plan.md §6 exactly (that table already assumed MySQL-compatible types); only the storage engine changes from SQLite to MySQL. Later objectives (documents, query_logs, etc.) migrate onto this same MySQL database without further schema changes to `users`.

`email` uniqueness is enforced at the DB level (`UNIQUE KEY`) as the source of truth; the API also checks and returns a friendly `409` before hitting the DB constraint.

## 3. REST API — `/api/v1/auth`

Same envelope as implementation-plan.md §4: JSON body, `Authorization: Bearer <JWT>`, shared error shape:

```json
{ "error": { "code": "validation_error", "message": "email is required" } }
```

Codes used here: `validation_error` (400), `unauthorized` (401), `conflict` (409), `server_error` (500).

### `POST /api/v1/auth/register`

Request:
```json
{ "name": "Jane Student", "email": "jane@uni.edu", "password": "at-least-8-chars" }
```

Validation: `name` non-empty (≤120 chars); `email` valid format (≤190 chars); `password` ≥ 8 chars. Any failure → `400 validation_error` naming the first offending field. Existing email → `409 conflict`.

Response `201`:
```json
{
  "user": { "id": 1, "name": "Jane Student", "email": "jane@uni.edu", "role": "student", "created_at": "2026-08-06T10:00:00Z" },
  "access_token": "<jwt>"
}
```

Role is always `student`; password is bcrypt-hashed before storage; `created_at` set by the DB default.

### `POST /api/v1/auth/login`

Request: `{ "email": "jane@uni.edu", "password": "..." }`

Response `200`: same shape as register's response. Wrong email or password → `401 unauthorized` with a single generic message ("invalid email or password") — deliberately not distinguishing which field was wrong, to avoid leaking which emails are registered. Successful login updates `last_login_at`.

### `GET /api/v1/auth/me`

Requires `Authorization: Bearer <JWT>`. No token / expired / malformed → `401 unauthorized`.

Response `200`: `{ "user": { "id": 1, "name": "...", "email": "...", "role": "student", "created_at": "..." } }`

## 4. Frontend design

### 4.1 Color theme

| Token | Hex | Use |
|---|---|---|
| `--color-bg` | `#FFFFFF` | page background |
| `--color-surface` | `#F7FAF7` | card/panel background |
| `--color-primary` | `#1E7A34` | primary buttons, links, focus ring |
| `--color-primary-hover` | `#166028` | button hover |
| `--color-primary-light` | `#E3F3E6` | subtle backgrounds, selected states |
| `--color-accent` | `#F5A524` | secondary CTA, highlights, badges |
| `--color-accent-hover` | `#D98E14` | accent hover |
| `--color-text` | `#1A1F1B` | body text |
| `--color-text-muted` | `#5B6660` | secondary text |
| `--color-border` | `#D8E3DA` | input borders, dividers |
| `--color-error` | `#C0392B` | validation errors |

Contrast checked: `--color-primary` on `--color-bg` and white text on `--color-primary` both clear WCAG AA for normal text.

### 4.2 Routes

| Path | Component | Access |
|---|---|---|
| `/` | `LoginPage` | public — the app's entry point |
| `/register` | `RegisterPage` | public |
| `/dashboard` | `DashboardPage` (placeholder, role-aware greeting) | protected — redirects to `/` if no valid token |

### 4.3 Structure

```
frontend/src/
  api/client.js          fetch wrapper: base URL, attaches Bearer token, parses {error} envelope
  context/AuthContext.jsx  holds {user, token}, login(), register(), logout(), persists token to localStorage, restores session via /auth/me on load
  components/
    Button.jsx, TextField.jsx, Card.jsx, Alert.jsx   theme-aware primitives
  pages/
    LoginPage.jsx
    RegisterPage.jsx
    DashboardPage.jsx
  routes/ProtectedRoute.jsx   redirects to "/" when unauthenticated
  styles/theme.css        CSS variables from §4.1
  App.jsx                 router setup
  main.jsx
```

## 5. Validation against constraints

- No OTP/SMS anywhere in the flow — confirmed, only email+password. ✅
- JWT retained — confirmed, flask-jwt-extended issues the access token. ✅
- MySQL via XAMPP — confirmed, PyMySQL connection string points at XAMPP's default MySQL instance. ✅
- Login as entry point — confirmed, `/` route. ✅
- Color theme white/green/yellow-orange — confirmed, palette in §4.1. ✅
- Matches existing `users` schema in implementation-plan.md §6 — confirmed, no drift for later objectives. ✅

## 6. Follow-ups (not in this slice)

- Rate limiting on `/auth/login` (brute-force protection) — worth adding once the admin module lands.
- Password reset flow — explicitly out of scope (would normally need email/OTP, which this brief excludes); revisit if the project needs it later.
