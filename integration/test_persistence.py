"""Durability across restarts — the reason Postgres is in the stack at all.

The unit suite runs on an in-memory SQLite database that is thrown away
between tests, so "does the data still exist afterwards?" is a question it
cannot ask. These tests restart and recreate containers for real.
"""

from __future__ import annotations

import json

from websockets.sync.client import connect

from conftest import API, compose, node_op, psql, recv_until, room_url, wait_until_healthy


def _draw_on_canvas(room: dict, label: str) -> None:
    with connect(
        room_url(room["sessionId"], room["ownerParticipantId"]),
        additional_headers={"Cookie": room["ownerCookie"]},
    ) as ws:
        recv_until(ws, "room_joined")
        ws.send(json.dumps({"type": "ops", "ops": [node_op(label)]}))
        recv_until(ws, "document_update")


def test_sessions_and_canvas_survive_an_app_restart(owner_client, room):
    _draw_on_canvas(room, "Survives restart")

    compose("restart", "app")
    wait_until_healthy()

    session = owner_client.get(f"{API}/sessions/{room['sessionId']}")
    assert session.status_code == 200
    assert session.json()["title"] == "Realtime room"

    elements = owner_client.get(f"{API}/sessions/{room['sessionId']}/canvas").json()["elements"]
    assert any(e.get("label") == "Survives restart" for e in elements)


def test_participant_bearer_token_survives_an_app_restart(owner_client, room):
    """Tokens live in Postgres, not process memory — a restart must not sign everyone out."""
    compose("restart", "app")
    wait_until_healthy()

    auth = {"Authorization": f"Bearer {room['candidateToken']}"}
    r = owner_client.get(f"{API}/sessions/{room['sessionId']}/canvas", headers=auth)
    assert r.status_code == 200


def test_seed_data_is_not_reapplied_on_restart(owner_client):
    """The lifespan hook seeds only when the users table is empty.

    If that guard broke, every restart would duplicate the demo sessions or
    fail on a primary key collision and take the container down.
    """
    before = (psql("select count(*) from users"), psql("select count(*) from sessions"))

    compose("restart", "app")
    wait_until_healthy()

    assert (psql("select count(*) from users"), psql("select count(*) from sessions")) == before


def test_data_survives_recreating_the_containers(owner_client):
    """`down` without `-v` keeps the named volume; the database must come back."""
    created = owner_client.post(
        f"{API}/sessions", json={"title": "Outlives its container", "prompt": "volume check"}
    ).json()["id"]

    compose("down")
    wait_until_healthy()

    titles = {s["title"] for s in owner_client.get(f"{API}/sessions").json()}
    assert "Outlives its container" in titles
    assert psql(f"select title from sessions where id = '{created}'") == "Outlives its container"


def test_app_recovers_when_the_database_restarts_under_it(owner_client):
    """Postgres going away must not leave the app permanently broken.

    Eventual recovery, not immediate: the engine is built without
    `pool_pre_ping`, so connections pooled before the restart are handed out
    once more and fail. Adding `pool_pre_ping=True` in `app/database.py` would
    make the very first request succeed too.
    """
    compose("restart", "db")
    wait_until_healthy()

    statuses = [owner_client.get(f"{API}/sessions").status_code for _ in range(5)]
    assert 200 in statuses, f"never recovered after the database restart: {statuses}"
