from app.store import store


def test_join_with_unknown_token(client):
    r = client.post("/api/v1/join", json={"token": "nope", "displayName": "Sam"})
    assert r.status_code == 404
    assert r.json()["code"] == "link_invalid"


def test_join_with_revoked_token(client):
    store.links["lnk_seed"].revokedAt = "2020-01-01T00:00:00.000Z"
    r = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam"})
    assert r.status_code == 403
    assert r.json()["code"] == "link_revoked"


def test_join_with_expired_token(client):
    store.links["lnk_seed"].expiresAt = "2020-01-01T00:00:00.000Z"
    r = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam"})
    assert r.status_code == 403
    assert r.json()["code"] == "link_expired"


def test_join_archived_session(client):
    store.sessions["ses_ratelimiter"].state = "archived"
    r = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam"})
    assert r.status_code == 403
    assert r.json()["code"] == "session_archived"


def test_join_ended_session(client):
    store.sessions["ses_ratelimiter"].state = "ended"
    r = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam"})
    assert r.status_code == 403
    assert r.json()["code"] == "session_ended"


def test_join_at_capacity(client):
    # capacity counts *all* active participants of the session, and the seed data
    # already has the owner present, so maxUses=2 allows exactly one more guest.
    store.links["lnk_seed"].maxUses = 2
    r1 = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam Okafor"})
    assert r1.status_code == 200

    r2 = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Alex Kim"})
    assert r2.status_code == 409
    assert r2.json()["code"] == "session_full"


def test_join_name_too_short(client):
    r = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "A"})
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_display_name"


def test_join_success_trims_and_truncates_name_and_returns_bearer_token(client):
    long_name = "  " + ("Sam " * 15) + "  "
    r = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": long_name})
    assert r.status_code == 200
    body = r.json()
    assert len(body["participant"]["displayName"]) <= 40
    assert body["participant"]["role"] == "candidate"
    assert body["participant"]["userId"] is None
    assert "participantToken" in body and len(body["participantToken"]) > 10


def test_join_as_owner_is_idempotent(owner_client):
    r1 = owner_client.post("/api/v1/sessions/ses_cdn/participants/me")
    assert r1.status_code == 200
    p1 = r1.json()["participant"]

    r2 = owner_client.post("/api/v1/sessions/ses_cdn/participants/me")
    p2 = r2.json()["participant"]
    assert p1["id"] == p2["id"]
    assert p1["role"] == "owner"


def test_join_as_owner_requires_auth(client):
    r = client.post("/api/v1/sessions/ses_cdn/participants/me")
    assert r.status_code == 401


def test_list_participants_readable_by_bearer_token(client):
    join = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam Okafor"}).json()
    token = join["participantToken"]

    r = client.get(
        "/api/v1/sessions/ses_ratelimiter/participants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert join["participant"]["id"] in ids
    assert "pt_owner" in ids


def test_list_participants_forbidden_without_credentials(client):
    r = client.get("/api/v1/sessions/ses_ratelimiter/participants")
    assert r.status_code == 403


def test_remove_participant(owner_client, client):
    join = client.post("/api/v1/join", json={"token": "demo-candidate-token", "displayName": "Sam Okafor"}).json()
    pid = join["participant"]["id"]

    r = owner_client.delete(f"/api/v1/sessions/ses_ratelimiter/participants/{pid}")
    assert r.status_code == 204

    remaining = owner_client.get("/api/v1/sessions/ses_ratelimiter/participants").json()
    assert pid not in {p["id"] for p in remaining}

    # their bearer token is now dead
    r2 = client.get(
        "/api/v1/sessions/ses_ratelimiter/participants",
        headers={"Authorization": f"Bearer {join['participantToken']}"},
    )
    assert r2.status_code == 403


def test_remove_participant_owner_only(client):
    r = client.delete("/api/v1/sessions/ses_ratelimiter/participants/pt_owner")
    assert r.status_code == 403


def test_remove_unknown_participant(owner_client):
    r = owner_client.delete("/api/v1/sessions/ses_ratelimiter/participants/pt_nope")
    assert r.status_code == 404
