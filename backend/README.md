# Linewarmer backend

FastAPI implementation of `../openapi.yaml` — the contract
`frontend/src/services/api.ts` expects. In-memory store only, seeded with the
same demo data as the frontend mock (`frontend/src/services/mock/store.ts`),
so the app has something to show without a database.

## Run

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8091
```

Or from the repo root: `make backend` (or `make dev` to run backend + frontend together).

API is mounted at `/api/v1`, matching the `servers` entry in the spec. Docs
at `/docs`.

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
  main.py       FastAPI app, CORS, error handlers, router registration
  models.py     Pydantic schemas mirroring openapi.yaml components
  store.py      In-memory state + seed data
  service.py    Business logic (mirrors mockApi.ts behaviour exactly)
  deps.py       Auth dependencies (cookie session, bearer participant token)
  security.py   Password hashing, token hashing
  canvas_ops.py Canvas op application (upsert/delete/clear), LWW merge
  realtime.py   WebSocket room connection/presence manager
  routers/      One module per resource, plus the realtime websocket route
```
