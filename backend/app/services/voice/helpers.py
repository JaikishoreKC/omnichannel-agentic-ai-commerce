from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def normalize_backoff_list(raw: Any) -> list[int]:
    values: list[int] = []
    if isinstance(raw, list):
        source = raw
    elif isinstance(raw, str):
        source = [part.strip() for part in raw.split(",")]
    elif raw is None:
        source = []
    else:
        source = [raw]
    for value in source:
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            values.append(parsed)
    if not values:
        return [60, 300, 900]
    return values

def extract_provider_call_id(payload: dict[str, Any]) -> str | None:
    direct_keys = ("call_id", "callId", "id", "uuid")
    containers: list[dict[str, Any]] = [payload]
    for key in ("data", "call", "payload"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    for container in containers:
        for key in direct_keys:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None

def extract_provider_event_id(payload: dict[str, Any]) -> str | None:
    keys = ("event_id", "eventId", "webhook_id", "webhookId", "message_id", "messageId")
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None

def provider_event_key(payload: dict[str, Any], superu_client: Any) -> str:
    event_id = extract_provider_event_id(payload)
    if event_id:
        return event_id
    fingerprint_fn = getattr(superu_client, "payload_fingerprint", None)
    if callable(fingerprint_fn):
        try:
            value = str(fingerprint_fn(payload)).strip()
            if value:
                return value
        except (RuntimeError, ValueError, TypeError):
            value = ""
    try:
        # Use narrow exceptions
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        canonical = str(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def normalize_provider_status(payload: dict[str, Any]) -> str:
    raw = (
        payload.get("status")
        or payload.get("call_status")
        or payload.get("state")
        or payload.get("event")
        or ""
    )
    value = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"queued", "dialing", "ringing"}:
        return "ringing"
    if value in {"connected", "answered", "in_progress", "active"}:
        return "in_progress"
    if value in {"completed", "success", "ended", "done"}:
        return "completed"
    if value in {
        "failed",
        "error",
        "busy",
        "cancelled",
        "canceled",
        "no_answer",
        "voicemail",
        "dropped",
        "timeout",
    }:
        return "failed"
    return "in_progress"

def extract_outcome(payload: dict[str, Any]) -> str:
    for key in ("outcome", "disposition", "result", "intent"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalize_provider_status(payload)
