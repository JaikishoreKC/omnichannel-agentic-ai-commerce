from __future__ import annotations

from fastapi.testclient import TestClient

from app.container import settings
from app.main import app


def test_http_responses_include_security_headers() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in str(response.headers.get("Content-Security-Policy", ""))


def test_mutating_endpoint_rejects_non_json_content_type() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/login",
        headers={"Content-Type": "text/plain"},
        content=b'{"email":"admin@example.com","password":"AdminPass123!"}',
    )
    assert response.status_code == 415


def test_request_body_size_limit_is_enforced() -> None:
    previous_limit = settings.request_max_body_bytes
    try:
        object.__setattr__(settings, "request_max_body_bytes", 32)
        client = TestClient(app)
        response = client.post(
            "/v1/auth/login",
            json={
                "email": "admin@example.com",
                "password": "AdminPass123!",
                "pad": "x" * 200,
            },
        )
        assert response.status_code == 413
    finally:
        object.__setattr__(settings, "request_max_body_bytes", previous_limit)


def test_duplicate_critical_headers_are_rejected() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/login",
        headers=[
            ("Content-Type", "application/json"),
            ("X-Session-Id", "session_a"),
            ("X-Session-Id", "session_b"),
        ],
        content=b'{"email":"admin@example.com","password":"AdminPass123!"}',
    )
    assert response.status_code == 400
