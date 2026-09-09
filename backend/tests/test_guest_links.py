def test_list_guest_links_excludes_revoked_and_is_owner_only(owner_client, client):
    r = client.get("/api/v1/sessions/ses_ratelimiter/guest-links")
    assert r.status_code == 403

    r2 = owner_client.get("/api/v1/sessions/ses_ratelimiter/guest-links")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["token"] == "demo-candidate-token"


def test_create_guest_link_defaults_and_rotates(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_ratelimiter/guest-links", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["roleGranted"] == "candidate"
    assert body["maxUses"] == 10
    assert body["uses"] == 0
    assert body["revokedAt"] is None
    assert len(body["token"]) >= 32

    links = owner_client.get("/api/v1/sessions/ses_ratelimiter/guest-links").json()
    tokens = {l["token"] for l in links}
    assert "demo-candidate-token" not in tokens
    assert body["token"] in tokens
    assert len(links) == 1


def test_create_guest_link_with_no_body(owner_client):
    r = owner_client.post("/api/v1/sessions/ses_ratelimiter/guest-links")
    assert r.status_code == 201
    assert r.json()["roleGranted"] == "candidate"


def test_create_guest_link_observer_role_independent_of_candidate(owner_client):
    owner_client.post("/api/v1/sessions/ses_ratelimiter/guest-links", json={"role": "observer"})
    links = owner_client.get("/api/v1/sessions/ses_ratelimiter/guest-links").json()
    roles = {l["roleGranted"] for l in links}
    assert roles == {"candidate", "observer"}


def test_revoke_guest_link(owner_client):
    created = owner_client.post("/api/v1/sessions/ses_ratelimiter/guest-links", json={}).json()
    r = owner_client.delete(f"/api/v1/sessions/ses_ratelimiter/guest-links/{created['id']}")
    assert r.status_code == 204

    links = owner_client.get("/api/v1/sessions/ses_ratelimiter/guest-links").json()
    assert created["id"] not in {l["id"] for l in links}


def test_revoke_unknown_guest_link(owner_client):
    r = owner_client.delete("/api/v1/sessions/ses_ratelimiter/guest-links/lnk_nope")
    assert r.status_code == 404


def test_revoke_guest_link_owner_only(client):
    r = client.delete("/api/v1/sessions/ses_ratelimiter/guest-links/lnk_seed")
    assert r.status_code == 403
