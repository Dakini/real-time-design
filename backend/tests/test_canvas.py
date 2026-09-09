def test_get_canvas_returns_seeded_snapshot(owner_client):
    r = owner_client.get("/api/v1/sessions/ses_ratelimiter/canvas")
    assert r.status_code == 200
    body = r.json()
    assert body["sessionId"] == "ses_ratelimiter"
    assert body["cursor"] == 0
    assert len(body["elements"]) == 8


def test_get_canvas_forbidden_for_stranger(client):
    r = client.get("/api/v1/sessions/ses_ratelimiter/canvas")
    assert r.status_code == 403


def test_get_canvas_readable_by_guest_token(client):
    join = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam Okafor"}).json()
    r = client.get(
        "/api/v1/sessions/ses_ratelimiter/canvas",
        headers={"Authorization": f"Bearer {join['participantToken']}"},
    )
    assert r.status_code == 200


def test_clear_canvas_owner_only(client):
    r = client.post("/api/v1/sessions/ses_ratelimiter/canvas/clear", json={"actorId": "pt_owner"})
    assert r.status_code == 403


def test_clear_canvas_empties_elements(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_ratelimiter/canvas/clear", json={"actorId": "pt_owner"})
    assert r.status_code == 204

    snapshot = owner_client.get("/api/v1/sessions/ses_ratelimiter/canvas").json()
    assert snapshot["elements"] == []
    assert snapshot["cursor"] == 1
