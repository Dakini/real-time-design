# Linewarmer backend

FastAPI implementation of `../openapi.yaml` — the contract
`frontend/src/services/api.ts` expects. Persisted via SQLAlchemy, seeded on
first run with the same demo data as the frontend mock
(`frontend/src/services/mock/store.ts`), so the app has something to show
without any setup.

## Run

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8091
```

Or from the repo root: `make backend` (or `make dev` to run backend + frontend together).

API is mounted at `/api/v1`, matching the `servers` entry in the spec. Docs
at `/docs`.

## Database

`DATABASE_URL` selects the backend via any SQLAlchemy-supported URL; it
defaults to a local SQLite file (`backend/linewarmer.db`), created and seeded
automatically on first startup. The app is database-agnostic — nothing
outside `app/database.py` assumes SQLite — so pointing it at Postgres is just:

```bash
DATABASE_URL="postgresql+psycopg://user:pass@host:5432/linewarmer" uv run uvicorn app.main:app --port 8091
```

`psycopg[binary]` is already a dependency, so no extra install step is needed. Note that
SQLite doesn't enforce foreign keys by default while Postgres does — if you add new code that
inserts a row and a row referencing it (via FK) in the same transaction, call `db.flush()`
between the two so the parent row exists before the child is inserted (see `sign_in` and
`join_with_token` in `service.py` for examples).

## Test

```bash
uv run pytest
```

## Auth

- **Interviewers** sign in by email only (`POST /auth/sign-in`), upsert
  semantics per the spec — no sign-up screen. An optional `password` field
  is accepted: if the account is new it's set (hashed with salted
  PBKDF2-HMAC-SHA256), if the account exists and a password is supplied it's
  verified. The session credential is an opaque random token; only its
  SHA-256 digest is ever stored, and the raw value is set as the `lw_session`
  HttpOnly cookie.
- **Guests** redeem a one-time invite link (`POST /join`) and get back a
  `participantToken` bearer credential, scoped to one participant in one
  session. Same hash-at-rest treatment as session tokens.
- Set `COOKIE_SECURE=true` when serving over HTTPS in production — it
  defaults to `false` so local dev and tests over plain HTTP work.
- `CORS_ORIGINS` is a comma-separated allowlist (defaults to the common
  Vite/CRA local dev ports).

## Layout

```
app/
  main.py       FastAPI app, CORS, error handlers, router registration, DB init
  models.py     Pydantic schemas mirroring openapi.yaml components (the API shape)
  db_models.py  SQLAlchemy ORM models (the storage shape)
  database.py   Engine/session setup, DATABASE_URL handling
  seed.py       Demo data, inserted into an empty database on first run
  clock.py      Timestamp helpers (now_iso, now_ms)
  service.py    Business logic (mirrors mockApi.ts behaviour exactly)
  deps.py       Auth dependencies (cookie session, bearer participant token)
  security.py   Password hashing, token hashing
  canvas_ops.py Canvas op application (upsert/delete/clear), LWW merge
  realtime.py   WebSocket room connection/presence manager
  routers/      One module per resource, plus the realtime websocket route
```
