def test_list_sessions_requires_auth(client):
    r = client.get("/api/v1/sessions")
    assert r.status_code == 401


def test_list_sessions_excludes_archived_and_sorts_by_updated_desc(owner_client):
    r = owner_client.get("/api/v1/sessions")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert "ses_ratelimiter" in ids
    assert "ses_chatscale" in ids
    assert "ses_cdn" in ids
    updated = [s["updatedAt"] for s in r.json()]
    assert updated == sorted(updated, reverse=True)


def test_create_session_trims_and_defaults_title(owner_client):
    r = owner_client.post("/api/v1/sessions", json={"title": "  ", "prompt": "  design something  "})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Untitled interview"
    assert body["prompt"] == "design something"
    assert body["state"] == "draft"
    assert body["candidateEditingEnabled"] is True
    assert body["cursorsVisible"] is True
    assert body["startedAt"] is None
    assert body["endedAt"] is None


def test_create_session_requires_auth(client):
    r = client.post("/api/v1/sessions", json={"title": "x", "prompt": "y"})
    assert r.status_code == 401


def test_get_session_forbidden_for_stranger(client):
    r = client.get("/api/v1/sessions/ses_ratelimiter")
    assert r.status_code == 403


def test_get_session_ok_for_owner(owner_client):
    r = owner_client.get("/api/v1/sessions/ses_ratelimiter")
    assert r.status_code == 200
    assert r.json()["id"] == "ses_ratelimiter"


def test_get_session_not_found(owner_client):
    r = owner_client.get("/api/v1/sessions/ses_nope")
    assert r.status_code == 404


def test_patch_session_sparse_update(owner_client):
    r = owner_client.patch("/api/v1/sessions/ses_ratelimiter", json={"candidateEditingEnabled": False})
    assert r.status_code == 200
    body = r.json()
    assert body["candidateEditingEnabled"] is False
    # untouched fields remain
    assert body["title"] == "Design a global rate limiter"


def test_patch_session_requires_at_least_one_field(owner_client):
    r = owner_client.patch("/api/v1/sessions/ses_ratelimiter", json={})
    assert r.status_code == 400


def test_patch_session_owner_only(client):
    r = client.patch("/api/v1/sessions/ses_ratelimiter", json={"title": "hijacked"})
    assert r.status_code == 403


def test_start_session_sets_started_at_once(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_cdn/start")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "live"
    started_at = body["startedAt"]
    assert started_at is not None

    r2 = owner_client.post("/api/v1/sessions/ses_cdn/start")
    assert r2.json()["startedAt"] == started_at


def test_start_session_conflict_when_ended(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_chatscale/start")
    assert r.status_code == 409


def test_end_session_forces_editing_off(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_ratelimiter/end")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "ended"
    assert body["candidateEditingEnabled"] is False
    assert body["endedAt"] is not None


def test_archive_session_removes_from_list(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_cdn/archive")
    assert r.status_code == 200
    assert r.json()["state"] == "archived"

    r2 = owner_client.get("/api/v1/sessions")
    ids = [s["id"] for s in r2.json()]
    assert "ses_cdn" not in ids


def test_duplicate_session_copies_canvas_not_lifecycle(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_ratelimiter/duplicate")
    assert r.status_code == 201
    body = r.json()
    assert body["id"] != "ses_ratelimiter"
    assert body["title"] == "Design a global rate limiter (copy)"
    assert body["state"] == "draft"
    assert body["startedAt"] is None

    canvas = owner_client.get(f"/api/v1/sessions/{body['id']}/canvas").json()
    original_canvas = owner_client.get("/api/v1/sessions/ses_ratelimiter/canvas").json()
    assert len(canvas["elements"]) == len(original_canvas["elements"])


def test_session_mutations_owner_only(client):
    for path in ["start", "end", "archive", "duplicate"]:
        r = client.post(f"/api/v1/sessions/ses_ratelimiter/{path}")
        assert r.status_code == 403, path
