# syntax=docker/dockerfile:1

# ---- Frontend build ------------------------------------------------------
FROM node:22-alpine AS frontend-build
WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
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
