"""Integration tests against the real docker compose stack.

Unlike `backend/tests`, which drive the ASGI app in-process against an
in-memory SQLite database, these tests build the image, bring up Postgres and
the app with `docker compose`, and talk to the published port over real HTTP
and WebSockets. They cover what the unit suite structurally cannot: the image
build, the frontend bundle the backend serves, Postgres as the store, and
durability across restarts.

Run with `make test-integration`. Environment overrides:

    APP_PORT=8100       host port the app is published on
    PG_PORT=55432       host port Postgres is published on
    IT_KEEP_STACK=1     leave the stack running afterwards, for debugging
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yaml"
OVERLAY_FILE = REPO_ROOT / "docker-compose.integration.yaml"
PROJECT = "linewarmer-it"

APP_PORT = int(os.environ.get("APP_PORT", "8100"))
BASE_URL = f"http://127.0.0.1:{APP_PORT}"
API = f"{BASE_URL}/api/v1"
WS_BASE = f"ws://127.0.0.1:{APP_PORT}/api/v1"

# Deliberately not 5432: a dev Postgres (`make postgres`) commonly holds that,
# and the app container reaches the database over the compose network anyway,
# so the published port only exists for host-side poking.
PG_PORT = os.environ.get("PG_PORT", "55432")

SEED_OWNER_EMAIL = "jordan@linewarmer.io"
SEED_OWNER_PASSWORD = "linewarmer-demo"

# `up --build` runs `npm ci` plus a Vite build on a cold cache.
BUILD_TIMEOUT = 900


def _compose_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("APP_PORT", str(APP_PORT))
    env["PG_PORT"] = PG_PORT
    return env


def compose(*args: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "-f", str(OVERLAY_FILE), "-p", PROJECT, *args]
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=_compose_env(), capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        # capture_output hides stdout/stderr from CI logs by default; surface it
        # here so a build/healthcheck failure is diagnosable instead of just a
        # bare "returned non-zero exit status" from CalledProcessError.
        print(result.stdout)
        print(result.stderr)
        result.check_returncode()
    return result


def compose_up() -> None:
    """Bring the stack up and block until both healthchecks pass."""
    compose("up", "--build", "-d", "--wait", "--wait-timeout", "180", timeout=BUILD_TIMEOUT)


def psql(sql: str) -> str:
    """Run a query directly against the database container.

    Via `compose exec` rather than a host connection, so the assertions do not
    depend on the published Postgres port or a host-side driver.
    """
    user = os.environ.get("POSTGRES_USER", "sdip")
    db = os.environ.get("POSTGRES_DB", "sdip")
    result = compose("exec", "-T", "db", "psql", "-U", user, "-d", db, "-tAc", sql)
    return result.stdout.strip()


def service_state(service: str) -> dict:
    """The `docker compose ps` record for one service."""
    out = compose("ps", "--format", "json", service).stdout.strip()
    # Compose emits either a JSON array or newline-delimited objects depending
    # on version; normalise both to a single record.
    if out.startswith("["):
        records = json.loads(out)
    else:
        records = [json.loads(line) for line in out.splitlines() if line.strip()]
    assert records, f"no running container for service {service!r}"
    return records[0]


def wait_until_healthy() -> None:
    compose("up", "-d", "--wait", "--wait-timeout", "180", timeout=300)


def _port_is_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


# ----------------------------------------------------------- websockets --

def room_url(session_id: str, participant_id: str, token: str | None = None) -> str:
    url = f"{WS_BASE}/sessions/{session_id}/room?participantId={participant_id}"
    return f"{url}&token={token}" if token else url


def recv_until(ws, message_type: str, limit: int = 10) -> dict:
    """Read past presence chatter to the message a test actually cares about."""
    for _ in range(limit):
        message = json.loads(ws.recv(timeout=10))
        if message["type"] == message_type:
            return message
    raise AssertionError(f"never received a {message_type!r} message")


def node_op(label: str) -> dict:
    """A well-formed `upsert` of a node element, ready to send on a room socket."""
    return {
        "clientOperationId": str(uuid.uuid4()),
        "op": {
            "type": "upsert",
            "element": {
                "kind": "node",
                "id": f"el_{uuid.uuid4().hex[:8]}",
                "componentType": "cache",
                "label": label,
                "description": "",
                "x": 10.0,
                "y": 20.0,
                "width": 160.0,
                "height": 60.0,
                # Both are server-assigned on commit; the client value is ignored.
                "createdBy": "unused",
                "updatedAt": 0,
            },
        },
    }


# --------------------------------------------------------------- stack --

@pytest.fixture(scope="session", autouse=True)
def stack():
    """Build and start the compose stack once for the whole suite.

    Torn down with `-v`, which is why the overlay renames the volume: a stray
    `down -v` against the real file would wipe the local dev database.
    """
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("docker is not available")

    # A previous aborted run may have left containers behind; start from scratch
    # so the "seeds an empty database" assertions mean something. Done before
    # the port check so our own leftovers free the port rather than fail it.
    compose("down", "-v", "--remove-orphans", check=False)

    if not _port_is_free(APP_PORT):
        pytest.fail(
            f"port {APP_PORT} is already in use — stop the dev stack (`make down`) "
            f"or run with APP_PORT=<other port>"
        )

    compose_up()
    try:
        yield
    finally:
        if os.environ.get("IT_KEEP_STACK") == "1":
            print(f"\nIT_KEEP_STACK=1 — stack left up on {BASE_URL}")
        else:
            compose("down", "-v", "--remove-orphans", check=False)


@pytest.fixture()
def client():
    """Anonymous HTTP client against the published app port."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0, follow_redirects=True) as c:
        yield c


@pytest.fixture()
def owner_client(client):
    """HTTP client signed in as the seeded interviewer, cookie jar included."""
    r = client.post(f"{API}/auth/sign-in", json={"email": SEED_OWNER_EMAIL, "password": SEED_OWNER_PASSWORD})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def room(owner_client):
    """A live session with the owner joined and a candidate holding a bearer token."""
    session_id = owner_client.post(
        f"{API}/sessions", json={"title": "Realtime room", "prompt": "collaborate"}
    ).json()["id"]
    owner_client.post(f"{API}/sessions/{session_id}/start")
    owner_participant = owner_client.post(f"{API}/sessions/{session_id}/participants/me").json()["participant"]
    guest_token = owner_client.post(f"{API}/sessions/{session_id}/guest-links").json()["token"]

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as candidate:
        joined = candidate.post(f"{API}/join", json={"token": guest_token, "displayName": "Sam"}).json()

    return {
        "sessionId": session_id,
        "ownerParticipantId": owner_participant["id"],
        "ownerCookie": f"lw_session={owner_client.cookies.get('lw_session')}",
        "candidateParticipantId": joined["participant"]["id"],
        "candidateToken": joined["participantToken"],
    }
