"""The compose stack itself: port mapping, healthchecks, and which database is live."""

from __future__ import annotations

import json

from conftest import API, APP_PORT, COMPOSE_FILE, compose, psql, service_state


def test_compose_publishes_app_on_the_expected_port():
    config = json.loads(compose("config", "--format", "json").stdout)
    published = [int(p["published"]) for p in config["services"]["app"]["ports"]]
    assert published == [APP_PORT]


def test_compose_defaults_the_app_port_to_8100():
    """The suite exports APP_PORT, so `compose config` cannot prove the default.

    Assert against the file itself: a checkout with nothing in the environment
    must land on 8100.
    """
    assert "${APP_PORT:-8100}:8000" in COMPOSE_FILE.read_text()


def test_both_services_report_healthy():
    """`depends_on: service_healthy` is only meaningful if the probes really pass."""
    assert service_state("db")["Health"] == "healthy"
    assert service_state("app")["Health"] == "healthy"


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_app_is_backed_by_postgres_not_the_sqlite_fallback(owner_client):
    """The single most valuable assertion here.

    An unset or malformed DATABASE_URL makes the backend fall back to a SQLite
    file inside the container, silently — the API keeps working and every unit
    test still passes. Only a round trip through psql proves otherwise.
    """
    r = owner_client.post(
        f"{API}/sessions", json={"title": "Postgres reachability probe", "prompt": "probe"}
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    assert psql(f"select title from sessions where id = '{session_id}'") == "Postgres reachability probe"


def test_schema_was_created_by_create_all():
    tables = psql(
        "select table_name from information_schema.tables "
        "where table_schema = 'public' order by table_name"
    ).splitlines()
    assert {
        "canvas_elements",
        "canvas_operations",
        "guest_links",
        "interviewer_session_tokens",
        "participants",
        "sessions",
        "users",
    } <= set(tables)
