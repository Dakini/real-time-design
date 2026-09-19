"""The single-image deploy: the backend serving the built frontend bundle.

None of this exists when the unit suite imports `app.main` — FRONTEND_DIST_DIR
points at a directory only the image has, so the static mount and SPA fallback
are unreachable outside a container.
"""

from __future__ import annotations

import re

from conftest import API


def test_index_html_is_served_at_root(client):
    """The Dockerfile renames Vite's `_shell.html`; without it this 404s."""
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<script" in r.text


def test_unknown_route_falls_back_to_the_spa_shell(client):
    """Client-side routes are not files on disk; a deep link must still boot the app."""
    r = client.get("/sessions/ses_ratelimiter")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<script" in r.text


def test_hashed_assets_are_served(client):
    index = client.get("/").text
    asset_paths = re.findall(r'["\'](/assets/[^"\']+\.js)["\']', index)
    assert asset_paths, "index.html references no /assets/*.js bundle"

    r = client.get(asset_paths[0])
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]


def test_bundle_calls_the_api_on_the_same_origin(client):
    """Vite inlines the API URL at build time, so it is baked into the image.

    Without the Dockerfile's `ARG VITE_API_URL` the key is simply absent from
    the inlined env object and `httpApi.ts` falls back to its dev default of
    http://localhost:8091 — every request from the browser then fails with
    ERR_CONNECTION_REFUSED, while every server-side test stays green.

    Asserting on the inlined value rather than the absence of the dev URL:
    Vite does not fold the `?? DEFAULT_API_URL` branch away, so that literal
    survives in the bundle as dead code either way.
    """
    index = client.get("/").text
    found = []
    for path in re.findall(r'["\'](/assets/[^"\']+\.js)["\']', index):
        found += re.findall(r"VITE_API_URL:\s*[\"'`]([^\"'`]*)[\"'`]", client.get(path).text)

    assert found, "VITE_API_URL was not inlined into any bundle — the build arg is missing"
    assert set(found) == {"/api/v1"}, f"bundle targets {set(found)} instead of the same origin"


def test_api_routes_are_not_shadowed_by_the_spa_fallback(client):
    """The catch-all is registered last; real API paths must still win."""
    r = client.get(f"{API}/sessions")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/json")
    assert set(r.json()) == {"code", "message"}


def test_openapi_and_docs_are_reachable(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
