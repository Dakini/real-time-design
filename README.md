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

To use Postgres instead, point `DATABASE_URL` at it (see `backend/README.md` for details):

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql+psycopg://user:pass@host:5432/linewarmer" \
  linewarmer
```

### Useful env vars

| Var | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./linewarmer.db` | Any SQLAlchemy-supported database URL |
| `CORS_ORIGINS` | common local Vite/CRA ports | Comma-separated allowlist |
| `COOKIE_SECURE` | `false` | Set `true` when serving over HTTPS |

## Local development (no Docker)

Runs the backend with reload and the Vite frontend dev server side by side:

```bash
make install   # uv sync (backend) + npm i (frontend)
make dev       # backend on :8091, frontend on :5173
```

See `backend/README.md` and `frontend/README.md` for details on each half.
