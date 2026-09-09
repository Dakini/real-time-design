from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import SessionLocal, init_db
from .db_models import UserRow
from .errors import AppError
from .routers import auth, canvas, guest_links, participants, realtime, sessions
from .seed import seed_demo_data


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    with SessionLocal() as db:
        if db.query(UserRow).first() is None:
            seed_demo_data(db)
            db.commit()
    yield


app = FastAPI(
    title="Linewarmer Interview API",
    version="1.0.0",
    summary="The backend contract expected by the Linewarmer frontend.",
    lifespan=_lifespan,
)

_default_origins = (
    "http://localhost:5173,http://localhost:3000,http://localhost:8080,"
    "http://127.0.0.1:5173,http://127.0.0.1:3000,http://127.0.0.1:8080"
)
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"code": "bad_request", "message": "Malformed or invalid request body."},
    )


router_prefix = "/api/v1"

app.include_router(auth.router, prefix=router_prefix)
app.include_router(sessions.router, prefix=router_prefix)
app.include_router(guest_links.router, prefix=router_prefix)
app.include_router(participants.router, prefix=router_prefix)
app.include_router(canvas.router, prefix=router_prefix)
app.include_router(realtime.router, prefix=router_prefix)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, bool]:
    return {"ok": True}


# Serve the built frontend (see ../../Dockerfile) as a single-server deploy.
# Absent in local dev, where the frontend runs on its own Vite dev server.
frontend_dir = Path(os.environ.get("FRONTEND_DIST_DIR", Path(__file__).resolve().parent.parent / "static"))

if frontend_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = frontend_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dir / "index.html")
