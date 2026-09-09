def test_me_returns_null_when_signed_out(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json() is None


def test_sign_in_upserts_by_email(client):
    r = client.post("/api/v1/auth/sign-in", json={"email": "new.hire@linewarmer.io"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new.hire@linewarmer.io"
    assert body["displayName"] == "new.hire"

    r2 = client.post("/api/v1/auth/sign-in", json={"email": "new.hire@linewarmer.io"})
    assert r2.json()["id"] == body["id"]


def test_sign_in_sets_session_and_me_reflects_it(client):
    r = client.post("/api/v1/auth/sign-in", json={"email": "jordan@linewarmer.io"})
    assert r.status_code == 200
    assert r.json()["id"] == "user_owner"

    r2 = client.get("/api/v1/auth/me")
    assert r2.status_code == 200
    assert r2.json()["id"] == "user_owner"


def test_sign_in_requires_email(client):
    r = client.post("/api/v1/auth/sign-in", json={})
    assert r.status_code == 400
    assert "code" in r.json() and "message" in r.json()


def test_sign_out_clears_session_and_is_idempotent(owner_client):
    r = owner_client.post("/api/v1/auth/sign-out")
    assert r.status_code == 204

    r2 = owner_client.get("/api/v1/auth/me")
    assert r2.json() is None

    r3 = owner_client.post("/api/v1/auth/sign-out")
    assert r3.status_code == 204


def test_sign_in_with_correct_password_for_seeded_owner(client):
    r = client.post("/api/v1/auth/sign-in", json={"email": "jordan@linewarmer.io", "password": "linewarmer-demo"})
    assert r.status_code == 200


def test_sign_in_with_wrong_password_rejected(client):
    r = client.post("/api/v1/auth/sign-in", json={"email": "jordan@linewarmer.io", "password": "wrong"})
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_credentials"
