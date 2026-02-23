from __future__ import annotations

from fastapi.testclient import TestClient

from app.container import store
from app.main import app


def _admin_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert login.status_code == 200
    token = login.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_activity_integrity_endpoint_detects_tampering() -> None:
    client = TestClient(app)
    headers = _admin_headers(client)

    update = client.put(
        "/v1/admin/voice/settings",
        headers=headers,
        json={"enabled": False},
    )
    assert update.status_code == 200

    healthy = client.get("/v1/admin/activity/integrity", headers=headers)
    assert healthy.status_code == 200
    assert healthy.json()["ok"] is True

    with store.lock:
        store.admin_activity_logs[-1]["action"] = "tampered_action"

    compromised = client.get("/v1/admin/activity/integrity", headers=headers)
    assert compromised.status_code == 200
    payload = compromised.json()
    assert payload["ok"] is False
    assert any(issue["error"] == "entry_hash_mismatch" for issue in payload["issues"])
