# Linewarmer

Linewarmer is a live system-design interview tool. An interviewer creates a session (a title,
prompt, and scheduled time — e.g. "design a global rate limiter"), shares a one-time guest
link, and both sides collaborate on a shared canvas of sticky notes, nodes, and connectors in
real time over WebSockets, with live cursors and presence. The interviewer controls session
state (scheduled → live → ended) and can toggle whether the candidate is allowed to edit.

The repo is a FastAPI backend (`backend/`) serving both the JSON API and a built TanStack Start
frontend (`frontend/`) as static files, so it ships as a single deployable service.

## Run with Docker

The `Dockerfile` builds the frontend, then bundles it into the backend image so a single
container serves everything.

```bash
docker build -t linewarmer .
docker run --rm -p 8000:8000 linewarmer
```

Open http://localhost:8000. API docs are at http://localhost:8000/docs.

Data is stored in a local SQLite file inside the container by default, so it resets whenever
the container is removed. To persist it across runs, mount a volume and point `DATABASE_URL`
at a file inside it:

```bash
docker run --rm -p 8000:8000 \
  -v linewarmer-data:/data \
  -e DATABASE_URL=sqlite:////data/linewarmer.db \
  linewarmer
```

### Postgres

The `psycopg` driver is bundled in the image, so Postgres needs no extra setup. Start a
database:

```bash
docker run -d \
  --name interview-canvas-db \
  -e POSTGRES_USER=sdip \
  -e POSTGRES_PASSWORD=sdip \
  -e POSTGRES_DB=sdip \
  -p 5432:5432 \
  -v interview-canvas-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
```

Then point the app at it. Both containers need to be on the same Docker network to resolve
each other by name:

```bash
docker network create linewarmer-net
docker network connect linewarmer-net interview-canvas-db

docker run --rm -p 8000:8000 \
  --network linewarmer-net \
  -e DATABASE_URL="postgresql+psycopg://sdip:sdip@interview-canvas-db:5432/sdip" \
  linewarmer
```

Tables are created and seeded automatically on first startup, same as SQLite.

> **The `+psycopg` suffix is required.** A plain `postgresql://` URL makes SQLAlchemy reach for
> `psycopg2`, which isn't installed, and startup fails. Use `postgresql+psycopg://`.

> **There's no migration tooling.** The schema is created with `create_all`, which only creates
> *missing* tables — it never alters existing ones. If a column type changes in
> `backend/app/db_models.py`, an existing database keeps the old type and you'll hit errors at
> runtime. Either apply the change by hand (`ALTER TABLE …`) or start from a fresh volume
> (`docker rm -f interview-canvas-db && docker volume rm interview-canvas-pgdata`).

### Useful env vars

| Var | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./linewarmer.db` | Any SQLAlchemy-supported database URL; use `postgresql+psycopg://…` for Postgres |
| `CORS_ORIGINS` | common local Vite/CRA ports | Comma-separated allowlist |
| `COOKIE_SECURE` | `false` | Set `true` when serving over HTTPS |

## Local development (no Docker)

Runs the backend with reload and the Vite frontend dev server side by side:

```bash
make install   # uv sync (backend) + npm i (frontend)
make dev       # backend on :8091, frontend on :5173
```

By default the backend uses the SQLite file at `backend/linewarmer.db`. To develop against a
Postgres container instead (started as above, with its port published to the host), export
`DATABASE_URL` **in the same shell** before starting the backend:

```bash
export DATABASE_URL="postgresql+psycopg://sdip:sdip@localhost:5432/sdip"
make backend
```

If that variable isn't set, the backend silently falls back to SQLite — which looks like your
Postgres data having vanished.

The frontend needs nothing database-related: it only talks to the backend's HTTP API, which it
expects at `http://localhost:8091/api/v1`. Override that only if the backend isn't on the
default port:

```bash
export VITE_API_URL="http://localhost:8091/api/v1"
```

See `backend/README.md` and `frontend/README.md` for details on each half.
