import os

# Must be set before any `app.*` module is imported, since app.database reads
# it at import time to build the engine. An in-memory DB keeps tests isolated
# from whatever DATABASE_URL is configured for local dev.
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, reset_db
from app.main import app
from app.seed import seed_demo_data


@pytest.fixture(autouse=True)
def reset_store():
    reset_db()
    with SessionLocal() as db:
        seed_demo_data(db)
        db.commit()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def owner_client():
    c = TestClient(app)
    r = c.post("/api/v1/auth/sign-in", json={"email": "jordan@linewarmer.io"})
    assert r.status_code == 200
    return c
