"""An interview end to end over real HTTP, on the deployed image."""

from __future__ import annotations

import httpx
import pytest

from conftest import API, BASE_URL, SEED_OWNER_EMAIL, SEED_OWNER_PASSWORD


def test_demo_data_is_seeded_on_an_empty_database(owner_client):
    """The lifespan hook seeds only when the users table is empty."""
    sessions = owner_client.get(f"{API}/sessions").json()
    assert {s["id"] for s in sessions} >= {"ses_ratelimiter", "ses_chatscale", "ses_cdn"}


def test_seeded_canvas_survived_the_json_column_roundtrip(owner_client):
    """`data` is a JSON column; Postgres and SQLite disagree about JSON typing."""
    snapshot = owner_client.get(f"{API}/sessions/ses_ratelimiter/canvas").json()
    kinds = {e["kind"] for e in snapshot["elements"]}
    assert kinds == {"node", "sticky", "connector"}
    sticky = next(e for e in snapshot["elements"] if e["kind"] == "sticky")
    assert sticky["x"] == 100 and isinstance(sticky["x"], float | int)


def test_sign_in_sets_an_httponly_session_cookie(client):
    r = client.post(
        f"{API}/auth/sign-in", json={"email": SEED_OWNER_EMAIL, "password": SEED_OWNER_PASSWORD}
    )
    assert r.status_code == 200
    assert "lw_session" in r.cookies
    assert "httponly" in r.headers["set-cookie"].lower()

    assert client.get(f"{API}/auth/me").json()["email"] == SEED_OWNER_EMAIL

    assert client.post(f"{API}/auth/sign-out").status_code == 204
    assert client.get(f"{API}/auth/me").json() is None


def test_wrong_password_is_rejected(client):
    r = client.post(f"{API}/auth/sign-in", json={"email": SEED_OWNER_EMAIL, "password": "nope"})
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_credentials"
    assert "lw_session" not in r.cookies


def test_sessions_require_authentication(client):
    assert client.get(f"{API}/sessions").status_code == 401


@pytest.fixture()
def interview(owner_client):
    """A fresh session the owner has joined, plus a guest link for it."""
    r = owner_client.post(
        f"{API}/sessions", json={"title": "Design a URL shortener", "prompt": "bit.ly, from scratch"}
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    joined = owner_client.post(f"{API}/sessions/{session_id}/participants/me").json()
    link = owner_client.post(f"{API}/sessions/{session_id}/guest-links", json={"role": "candidate"})
    assert link.status_code == 201, link.text

    return {
        "sessionId": session_id,
        "ownerParticipantId": joined["participant"]["id"],
        "guestToken": link.json()["token"],
    }


def test_candidate_joins_by_guest_link_and_reads_the_canvas(interview):
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as candidate:
        r = candidate.post(f"{API}/join", json={"token": interview["guestToken"], "displayName": "Sam"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["participant"]["role"] == "candidate"
        assert body["session"]["id"] == interview["sessionId"]

        # The candidate has no cookie — only the bearer token just issued.
        auth = {"Authorization": f"Bearer {body['participantToken']}"}
        assert candidate.get(f"{API}/sessions/{interview['sessionId']}/canvas").status_code == 403
        snapshot = candidate.get(f"{API}/sessions/{interview['sessionId']}/canvas", headers=auth)
        assert snapshot.status_code == 200
        assert snapshot.json()["sessionId"] == interview["sessionId"]


def test_a_stranger_cannot_read_someone_elses_session(interview):
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as stranger:
        stranger.post(f"{API}/auth/sign-in", json={"email": "mallory@example.com", "password": "x"})
        assert stranger.get(f"{API}/sessions/{interview['sessionId']}/canvas").status_code == 403
        assert stranger.get(f"{API}/sessions/{interview['sessionId']}").status_code == 403


def test_owner_drives_the_session_lifecycle(owner_client, interview):
    session_id = interview["sessionId"]

    started = owner_client.post(f"{API}/sessions/{session_id}/start").json()
    assert started["state"] == "live"
    assert started["startedAt"]

    patched = owner_client.patch(
        f"{API}/sessions/{session_id}", json={"candidateEditingEnabled": False}
    ).json()
    assert patched["candidateEditingEnabled"] is False

    ended = owner_client.post(f"{API}/sessions/{session_id}/end").json()
    assert ended["state"] == "ended"
    assert ended["endedAt"]


def test_revoked_guest_link_stops_working(owner_client, interview):
    session_id = interview["sessionId"]
    link_id = owner_client.get(f"{API}/sessions/{session_id}/guest-links").json()[0]["id"]
    assert owner_client.delete(f"{API}/sessions/{session_id}/guest-links/{link_id}").status_code == 204

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as candidate:
        r = candidate.post(f"{API}/join", json={"token": interview["guestToken"], "displayName": "Late"})
        assert r.status_code >= 400
        assert r.json()["code"]


def test_malformed_body_returns_the_error_contract(owner_client):
    r = owner_client.post(f"{API}/sessions", json={"title": "missing prompt"})
    assert r.status_code == 400
    assert r.json() == {"code": "bad_request", "message": "Malformed or invalid request body."}
