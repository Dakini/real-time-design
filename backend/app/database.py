"""Database engine and session setup.

`DATABASE_URL` selects the backing database via any SQLAlchemy-supported URL
(e.g. `sqlite:///./linewarmer.db`, `postgresql+psycopg://user:pass@host/db`).
Nothing else in the app assumes SQLite; swapping databases is just an env
var change plus installing the relevant driver.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .db_models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./linewarmer.db")


def _engine_kwargs(url: str) -> dict:
    if not url.startswith("sqlite"):
        return {}
    # SQLite connections are single-threaded by default; FastAPI may serve a
    # request on a different worker thread than the one that opened the
    # session, so this needs to be relaxed. An in-memory URL additionally
    # needs a single shared connection (StaticPool), or each new connection
    # would see a blank database.
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if ":memory:" in url or url == "sqlite://":
        kwargs["poolclass"] = StaticPool
    return kwargs


engine = create_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    """Test helper: drop and recreate every table."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
