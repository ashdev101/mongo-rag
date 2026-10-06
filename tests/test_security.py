"""Regression tests: HTTP method restriction, CORS, and security response headers.

These lock the security posture of the backend:
- only GET / HEAD / POST (+ OPTIONS for preflight) are accepted,
- DELETE / PUT / PATCH are rejected with 405,
- Access-Control-Allow-Methods reflects exactly the minimal verb set,
- security headers are attached to success, 405, and 500 responses.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.security import (
    SECURITY_HEADERS,
    add_head_support,
    add_restrict_methods,
    add_security_headers,
    configure_cors,
)

settings = get_settings()

ALLOWED_ORIGIN = settings.ALLOWED_ORIGINS[0].strip()
UNKNOWN_ORIGIN = "https://evil.example.com"

FORBIDDEN_METHODS = ("DELETE", "PUT", "PATCH")


@pytest.fixture()
def client():
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/messages")
    async def messages():
        return {"ok": True}

    @app.get("/api/boom")
    async def boom():
        raise RuntimeError("boom")

    # Same install order as main.py: head -> restrict -> security headers -> CORS
    add_head_support(app)
    add_restrict_methods(app)
    add_security_headers(app)
    configure_cors(app)

    return TestClient(app)


# --------------------------------------------------------------------------
# Method restriction
# --------------------------------------------------------------------------

@pytest.mark.parametrize("method", FORBIDDEN_METHODS)
def test_forbidden_methods_return_405(client, method):
    resp = client.request(method, "/api/health")
    assert resp.status_code == 405
    assert "detail" in resp.json()
    assert "GET" in resp.headers["Allow"]
    for forbidden in FORBIDDEN_METHODS:
        assert forbidden not in resp.headers["Allow"]


def test_allowed_methods_pass_through(client):
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/messages").status_code == 200


def test_head_is_allowed(client):
    resp = client.head("/api/health")
    assert resp.status_code == 200
    assert resp.content == b""


def test_head_on_post_only_route_is_405(client):
    assert client.head("/api/messages").status_code == 405


def test_allowed_methods_setting_is_minimal():
    assert settings.ALLOWED_METHODS == ["GET", "HEAD", "POST"]


# --------------------------------------------------------------------------
# CORS preflight
# --------------------------------------------------------------------------

def test_preflight_allows_only_minimal_methods(client):
    resp = client.options(
        "/api/messages",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, authorization",
        },
    )
    assert resp.status_code in (200, 204)
    advertised = {
        m.strip().upper()
        for m in resp.headers.get("access-control-allow-methods", "").split(",")
    }
    assert {"GET", "HEAD", "POST"} <= advertised
    assert advertised.isdisjoint({"DELETE", "PUT", "PATCH"})
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_preflight_rejects_unknown_origin(client):
    resp = client.options(
        "/api/messages",
        headers={
            "Origin": UNKNOWN_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


def test_actual_response_exposes_request_headers(client):
    resp = client.get("/api/health", headers={"Origin": ALLOWED_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    expose = resp.headers.get("access-control-expose-headers", "")
    assert "X-Request-ID" in expose
    assert "X-Process-Time" in expose


def test_405_still_carries_cors_and_security_headers(client):
    """CORS must wrap the method-restriction layer so 405s are readable by browsers."""
    resp = client.request("DELETE", "/api/health", headers={"Origin": ALLOWED_ORIGIN})
    assert resp.status_code == 405
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    for header in SECURITY_HEADERS:
        assert header in resp.headers


# --------------------------------------------------------------------------
# Security headers
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("method", "path", "expected_status"),
    [
        ("GET", "/api/health", 200),
        ("GET", "/api/does-not-exist", 404),
        ("DELETE", "/api/health", 405),
        ("GET", "/api/boom", 500),
    ],
)
def test_security_headers_on_every_response(client, method, path, expected_status):
    resp = client.request(method, path)
    assert resp.status_code == expected_status
    for header, value in SECURITY_HEADERS.items():
        assert resp.headers[header] == value


def test_500_is_generic(client):
    resp = client.get("/api/boom")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal Server Error"}
