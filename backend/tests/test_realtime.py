from app.store import store


def test_connect_rejects_unknown_participant(owner_client):
    with owner_client.websocket_connect("/api/v1/sessions/ses_ratelimiter/room?participantId=pt_ghost") as ws:
        msg = ws.receive_json()
        assert msg == {
            "type": "error",
            "code": "forbidden",
            "message": "You are not a participant of this session.",
        }


def test_owner_connect_receives_room_joined_then_presence(owner_client):
    with owner_client.websocket_connect("/api/v1/sessions/ses_ratelimiter/room?participantId=pt_owner") as ws:
        joined = ws.receive_json()
        assert joined["type"] == "room_joined"
        assert joined["snapshot"]["sessionId"] == "ses_ratelimiter"
        assert len(joined["snapshot"]["elements"]) == 8

        presence = ws.receive_json()
        assert presence["type"] == "presence_update"
        assert any(p["participantId"] == "pt_owner" for p in presence["presence"])


def test_ops_are_sequenced_and_deduped_by_client_operation_id(owner_client):
    with owner_client.websocket_connect("/api/v1/sessions/ses_ratelimiter/room?participantId=pt_owner") as ws:
        ws.receive_json()  # room_joined
        ws.receive_json()  # presence_update

        ws.send_json({"type": "ops", "ops": [{"clientOperationId": "cid-1", "op": {"type": "delete", "id": "el_goal"}}]})
        update = ws.receive_json()
        assert update["type"] == "document_update"
        assert len(update["ops"]) == 1
        assert update["ops"][0]["cursor"] == 1
        assert update["ops"][0]["clientOperationId"] == "cid-1"

        # resending the same clientOperationId must be a no-op
        ws.send_json({"type": "ops", "ops": [{"clientOperationId": "cid-1", "op": {"type": "delete", "id": "el_goal"}}]})
        update2 = ws.receive_json()
        assert update2["type"] == "document_update"
        assert update2["ops"] == []

    snapshot = owner_client.get("/api/v1/sessions/ses_ratelimiter/canvas").json()
    assert snapshot["cursor"] == 1
    assert "el_goal" not in {el["id"] for el in snapshot["elements"]}


def test_delete_prunes_attached_connectors(owner_client):
    with owner_client.websocket_connect("/api/v1/sessions/ses_ratelimiter/room?participantId=pt_owner") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "ops", "ops": [{"clientOperationId": "cid-del-gateway", "op": {"type": "delete", "id": "el_gateway"}}]})
        ws.receive_json()

    snapshot = owner_client.get("/api/v1/sessions/ses_ratelimiter/canvas").json()
    ids = {el["id"] for el in snapshot["elements"]}
    assert "el_gateway" not in ids
    # el_c1 (client->gateway) and el_c2 (gateway->cache) and el_c3 (gateway->db) must be pruned
    assert "el_c1" not in ids
    assert "el_c2" not in ids
    assert "el_c3" not in ids


def test_presence_update_is_sparse(owner_client):
    with owner_client.websocket_connect("/api/v1/sessions/ses_ratelimiter/room?participantId=pt_owner") as ws:
        ws.receive_json()
        ws.receive_json()

        ws.send_json({"type": "presence", "cursor": {"x": 10, "y": 20}})
        update = ws.receive_json()
        me = next(p for p in update["presence"] if p["participantId"] == "pt_owner")
        assert me["cursor"] == {"x": 10, "y": 20}
        assert me["selection"] == []

        ws.send_json({"type": "presence", "selection": ["el_client"]})
        update2 = ws.receive_json()
        me2 = next(p for p in update2["presence"] if p["participantId"] == "pt_owner")
        # cursor unchanged by the sparse selection-only patch
        assert me2["cursor"] == {"x": 10, "y": 20}
        assert me2["selection"] == ["el_client"]


def test_candidate_write_rejected_when_editing_disabled(client):
    join = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam Okafor"}).json()
    pid = join["participant"]["id"]
    token = join["participantToken"]

    store.sessions["ses_ratelimiter"].candidateEditingEnabled = False

    url = f"/api/v1/sessions/ses_ratelimiter/room?participantId={pid}"
    with client.websocket_connect(url, headers={"Authorization": f"Bearer {token}"}) as ws:
        ws.receive_json()  # room_joined
        ws.receive_json()  # presence_update

        ws.send_json({"type": "ops", "ops": [{"clientOperationId": "cid-x", "op": {"type": "delete", "id": "el_goal"}}]})
        err = ws.receive_json()
        assert err == {
            "type": "error",
            "code": "editing_locked",
            "message": "Editing is locked for you right now.",
        }
        resync = ws.receive_json()
        assert resync["type"] == "room_joined"


def test_candidate_can_write_when_editing_enabled(client):
    join = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam Okafor"}).json()
    pid = join["participant"]["id"]
    token = join["participantToken"]

    url = f"/api/v1/sessions/ses_ratelimiter/room?participantId={pid}"
    with client.websocket_connect(url, headers={"Authorization": f"Bearer {token}"}) as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "ops", "ops": [{"clientOperationId": "cid-y", "op": {"type": "delete", "id": "el_goal"}}]})
        update = ws.receive_json()
        assert update["type"] == "document_update"
        assert len(update["ops"]) == 1
