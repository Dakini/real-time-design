"""Collaboration over real WebSockets through the published container port.

The unit suite drives WebSockets through Starlette's TestClient, which never
performs an HTTP upgrade. These tests go over the wire, so they also cover
uvicorn's websocket implementation in the image and the cookie/`?token=`
handshake as a browser would do it.
"""

from __future__ import annotations

import json

from websockets.sync.client import connect

from conftest import API, node_op, recv_until, room_url


def test_owner_connects_with_the_session_cookie(room):
    """Browsers cannot set headers on a WS handshake, but they do send cookies."""
    with connect(
        room_url(room["sessionId"], room["ownerParticipantId"]),
        additional_headers={"Cookie": room["ownerCookie"]},
    ) as ws:
        joined = recv_until(ws, "room_joined")
        assert joined["snapshot"]["sessionId"] == room["sessionId"]


def test_candidate_connects_with_the_token_query_param(room):
    with connect(room_url(room["sessionId"], room["candidateParticipantId"], room["candidateToken"])) as ws:
        joined = recv_until(ws, "room_joined")
        assert joined["snapshot"]["sessionId"] == room["sessionId"]


def test_unauthenticated_connection_is_refused(room):
    with connect(room_url(room["sessionId"], room["ownerParticipantId"])) as ws:
        error = recv_until(ws, "error")
        assert error["code"] == "forbidden"


def test_edits_broadcast_between_two_participants(room):
    """The core promise of the product, over two real sockets."""
    with connect(
        room_url(room["sessionId"], room["ownerParticipantId"]),
        additional_headers={"Cookie": room["ownerCookie"]},
    ) as owner_ws, connect(
        room_url(room["sessionId"], room["candidateParticipantId"], room["candidateToken"])
    ) as candidate_ws:
        recv_until(candidate_ws, "room_joined")

        op = node_op("Redis")
        owner_ws.send(json.dumps({"type": "ops", "ops": [op]}))

        update = recv_until(candidate_ws, "document_update")
        assert update["ops"][0]["clientOperationId"] == op["clientOperationId"]
        assert update["ops"][0]["actorId"] == room["ownerParticipantId"]
        assert update["ops"][0]["op"]["element"]["label"] == "Redis"


def test_presence_lists_everyone_in_the_room(room):
    with connect(
        room_url(room["sessionId"], room["ownerParticipantId"]),
        additional_headers={"Cookie": room["ownerCookie"]},
    ) as owner_ws:
        recv_until(owner_ws, "room_joined")

        with connect(
            room_url(room["sessionId"], room["candidateParticipantId"], room["candidateToken"])
        ):
            presence = recv_until(owner_ws, "presence_update")
            while len(presence["presence"]) < 2:
                presence = recv_until(owner_ws, "presence_update")
            assert {p["participantId"] for p in presence["presence"]} == {
                room["ownerParticipantId"],
                room["candidateParticipantId"],
            }


def test_locking_editing_rejects_candidate_ops(owner_client, room):
    owner_client.patch(f"{API}/sessions/{room['sessionId']}", json={"candidateEditingEnabled": False})

    with connect(
        room_url(room["sessionId"], room["candidateParticipantId"], room["candidateToken"])
    ) as ws:
        recv_until(ws, "room_joined")
        ws.send(json.dumps({"type": "ops", "ops": [node_op("Sneaky edit")]}))

        error = recv_until(ws, "error")
        assert error["code"] == "editing_locked"


def test_ops_are_persisted_and_visible_over_http(owner_client, room):
    with connect(
        room_url(room["sessionId"], room["ownerParticipantId"]),
        additional_headers={"Cookie": room["ownerCookie"]},
    ) as ws:
        recv_until(ws, "room_joined")
        op = node_op("Load balancer")
        ws.send(json.dumps({"type": "ops", "ops": [op]}))
        recv_until(ws, "document_update")

    snapshot = owner_client.get(f"{API}/sessions/{room['sessionId']}/canvas").json()
    assert any(e["label"] == "Load balancer" for e in snapshot["elements"] if e["kind"] == "node")
    assert snapshot["cursor"] >= 1
