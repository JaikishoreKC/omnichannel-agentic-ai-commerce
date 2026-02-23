from __future__ import annotations

import hashlib
import hmac
import json
from time import time

from fastapi.testclient import TestClient

from app.container import settings, store
from app.main import app


def _sign(secret: str, timestamp: int, payload: dict[str, object]) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signed = str(timestamp).encode("utf-8") + b"." + body
    signature = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return body, signature


def _seed_call(provider_call_id: str) -> str:
    call_id = f"vcall_{store.next_id('item')}"
    with store.lock:
        store.voice_calls_by_id[call_id] = {
            "id": call_id,
            "recoveryKey": "rk_test",
            "userId": "",
            "sessionId": "session_test",
            "cartId": "cart_test",
            "status": "initiated",
            "attemptCount": 1,
            "attempts": [],
            "provider": "superu",
            "providerCallId": provider_call_id,
            "providerEventKeys": [],
            "providerEvents": [],
            "scriptVersion": "v1",
            "campaign": {},
            "outcome": "",
            "followupApplied": False,
            "estimatedCostUsd": 0.0,
            "createdAt": store.iso_now(),
            "updatedAt": store.iso_now(),
            "nextRetryAt": None,
            "lastError": None,
        }
    return call_id


def test_superu_callback_ingests_signed_event_idempotently() -> None:
    previous_secret = settings.superu_webhook_secret
    previous_tolerance = settings.superu_webhook_tolerance_seconds
    try:
        object.__setattr__(settings, "superu_webhook_secret", "test-webhook-secret")
        object.__setattr__(settings, "superu_webhook_tolerance_seconds", 600)

        provider_call_id = "provider_call_123"
        call_id = _seed_call(provider_call_id=provider_call_id)
        payload = {
            "event_id": "evt_123",
            "call_id": provider_call_id,
            "status": "completed",
            "outcome": "converted",
        }
        timestamp = int(time())
        body, signature = _sign("test-webhook-secret", timestamp, payload)
        headers = {
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": str(timestamp),
            "X-SuperU-Signature": signature,
        }

        client = TestClient(app)
        first = client.post("/v1/voice/superu/callback", headers=headers, content=body)
        assert first.status_code == 200
        assert first.json()["matched"] is True
        assert first.json()["idempotent"] is False

        second = client.post("/v1/voice/superu/callback", headers=headers, content=body)
        assert second.status_code == 200
        assert second.json()["matched"] is True
        assert second.json()["idempotent"] is True

        with store.lock:
            call = dict(store.voice_calls_by_id[call_id])
        assert call["status"] == "completed"
        assert "evt_123" in call["providerEventKeys"]
    finally:
        object.__setattr__(settings, "superu_webhook_secret", previous_secret)
        object.__setattr__(settings, "superu_webhook_tolerance_seconds", previous_tolerance)


def test_superu_callback_rejects_invalid_signature() -> None:
    previous_secret = settings.superu_webhook_secret
    previous_tolerance = settings.superu_webhook_tolerance_seconds
    try:
        object.__setattr__(settings, "superu_webhook_secret", "test-webhook-secret")
        object.__setattr__(settings, "superu_webhook_tolerance_seconds", 600)

        payload = {"event_id": "evt_bad", "call_id": "provider_call_999", "status": "completed"}
        timestamp = int(time())
        body, _ = _sign("test-webhook-secret", timestamp, payload)
        headers = {
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": str(timestamp),
            "X-SuperU-Signature": "invalid-signature",
        }

        client = TestClient(app)
        response = client.post("/v1/voice/superu/callback", headers=headers, content=body)
        assert response.status_code == 401
    finally:
        object.__setattr__(settings, "superu_webhook_secret", previous_secret)
        object.__setattr__(settings, "superu_webhook_tolerance_seconds", previous_tolerance)
