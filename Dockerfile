# syntax=docker/dockerfile:1

# ---- Frontend build ------------------------------------------------------
FROM node:22-alpine AS frontend-build
WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Vite inlines import.meta.env at build time, so the API URL is baked into the
# bundle here — it cannot be changed by an env var on `docker run`. The backend
# serves this bundle itself, so a same-origin relative path is correct and works
# whatever host/port the container is published on. Without this the bundle
# falls back to its dev default of http://localhost:8091, which the browser
# cannot reach from the container's port (ERR_CONNECTION_REFUSED).
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL

# Builds a static, client-hydrated SPA shell (tanstackStart.spa.enabled in
# vite.config.ts) instead of the Cloudflare SSR server — the FastAPI backend
# serves the resulting .output/public directory as plain static files.
RUN npm run build && mv .output/public/_shell.html .output/public/index.html

# ---- Backend --------------------------------------------------------------
FROM python:3.13-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/app ./app
COPY --from=frontend-build /frontend/.output/public ./static

ENV PATH="/app/.venv/bin:$PATH" \
    FRONTEND_DIST_DIR=/app/static \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
