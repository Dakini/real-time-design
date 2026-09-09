import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def owner_client():
    c = TestClient(app)
    r = c.post("/api/v1/auth/sign-in", json={"email": "jordan@linewarmer.io"})
    assert r.status_code == 200
    return c
