from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.superu_client import SuperUClient


class _DummyResponse:
    def __init__(self, payload: Any, *, error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> Any:
        return self._payload


def _settings(**overrides: Any) -> Settings:
    base = {
        "superu_enabled": True,
        "superu_api_key": "superu-key",
        "superu_assistant_id": "assistant_1",
        "superu_from_phone_number": "+15550001111",
    }
    base.update(overrides)
    return Settings(**base)


def _sign(secret: str, timestamp: int, body: bytes) -> str:
    signed = str(timestamp).encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()


def test_enabled_flag_checks_minimum_configuration() -> None:
    disabled = SuperUClient(settings=_settings(superu_enabled=False))
    assert disabled.enabled is False

    missing_key = SuperUClient(settings=_settings(superu_api_key=""))
    assert missing_key.enabled is False

    enabled = SuperUClient(settings=_settings())
    assert enabled.enabled is True


def test_start_outbound_call_requires_assistant_and_from_number() -> None:
    client = SuperUClient(
        settings=_settings(superu_assistant_id="", superu_from_phone_number="")
    )
    with pytest.raises(RuntimeError):
        client.start_outbound_call(to_phone_number="+15551234567")


def test_start_outbound_call_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, **kwargs: Any) -> _DummyResponse:
        captured["method"] = method
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _DummyResponse({"call_id": "call_1", "status": "queued"})

    monkeypatch.setattr(httpx, "request", fake_request)
    client = SuperUClient(settings=_settings())
    payload = client.start_outbound_call(
        to_phone_number="+15551234567",
        metadata={"cartId": "cart_1"},
    )
    assert payload["call_id"] == "call_1"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/api/v1/call/outbound-call")
    assert captured["kwargs"]["headers"]["superU-Api-Key"] == "superu-key"
    assert captured["kwargs"]["json"]["metadata"]["cartId"] == "cart_1"


def test_fetch_call_logs_extracts_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *_args, **_kwargs: _DummyResponse(
            {
                "logs": [
                    {"call_id": "call_1", "status": "ringing"},
                    {"call_id": "call_1", "status": "completed"},
                ]
            }
        ),
    )
    client = SuperUClient(settings=_settings())
    rows = client.fetch_call_logs(call_id="call_1", limit=5)
    assert len(rows) == 2
    assert rows[-1]["status"] == "completed"


def test_verify_webhook_signature_accepts_valid_payload() -> None:
    secret = "superu-webhook-secret"
    timestamp = 1_700_000_000
    body = b'{"call_id":"call_1","status":"completed"}'
    signature = _sign(secret, timestamp, body)
    client = SuperUClient(
        settings=_settings(
            superu_webhook_secret=secret,
            superu_webhook_tolerance_seconds=600,
        )
    )
    client.verify_webhook_signature(
        raw_body=body,
        signature_header=f"sha256={signature}",
        timestamp_header=str(timestamp),
        now_epoch=timestamp + 5,
    )


def test_verify_webhook_signature_rejects_bad_signature() -> None:
    client = SuperUClient(
        settings=_settings(
            superu_webhook_secret="superu-webhook-secret",
            superu_webhook_tolerance_seconds=600,
        )
    )
    with pytest.raises(ValueError):
        client.verify_webhook_signature(
            raw_body=b'{"call_id":"call_1"}',
            signature_header="sha256=bad-signature",
            timestamp_header="1700000000",
            now_epoch=1700000001,
        )


def test_verify_webhook_signature_rejects_stale_timestamp() -> None:
    secret = "superu-webhook-secret"
    timestamp = 1_700_000_000
    body = b'{"call_id":"call_1"}'
    signature = _sign(secret, timestamp, body)
    client = SuperUClient(
        settings=_settings(
            superu_webhook_secret=secret,
            superu_webhook_tolerance_seconds=10,
        )
    )
    with pytest.raises(ValueError):
        client.verify_webhook_signature(
            raw_body=body,
            signature_header=signature,
            timestamp_header=str(timestamp),
            now_epoch=timestamp + 60,
        )
