from __future__ import annotations
from copy import deepcopy
from typing import Any
from app.services.voice.outcome import apply_outcome_actions

def list_calls(store: Any, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 500))
    with store.lock:
        rows = list(store.voice_calls_by_id.values())
    if status:
        rows = [row for row in rows if str(row.get("status", "")) == status]
    rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
    return [deepcopy(row) for row in rows[:safe_limit]]

def record_call_event(
    *,
    job: dict[str, Any],
    cart: dict[str, Any] | None,
    user: dict[str, Any] | None,
    status: str,
    error: str | None,
    store: Any,
    voice_service: Any,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    provider_call_id: str | None = None,
    attempt_number: int | None = None,
    next_retry_at: str | None = None,
) -> None:
    call = get_or_create_call(job=job, cart=cart, user=user, store=store, voice_service=voice_service)
    attempt_index = attempt_number if attempt_number is not None else int(job.get("attempt", 0))
    event = {
        "attempt": max(1, attempt_index),
        "timestamp": store.iso_now(),
        "status": status,
        "error": error,
        "request": request_payload or {},
        "response": response_payload or {},
    }
    call.setdefault("attempts", []).append(event)
    call["attemptCount"] = len(call["attempts"])
    call["status"] = status
    call["updatedAt"] = store.iso_now()
    call["lastError"] = error
    call["nextRetryAt"] = next_retry_at
    if provider_call_id:
        call["providerCallId"] = provider_call_id
    with store.lock:
        store.voice_calls_by_id[str(call["id"])] = deepcopy(call)

def get_or_create_call(
    *,
    job: dict[str, Any],
    cart: dict[str, Any] | None,
    user: dict[str, Any] | None,
    store: Any,
    voice_service: Any,
) -> dict[str, Any]:
    recovery_key = str(job.get("recoveryKey", "")).strip()
    with store.lock:
        for existing in store.voice_calls_by_id.values():
            if str(existing.get("recoveryKey", "")) == recovery_key:
                return deepcopy(existing)

    settings = voice_service.get_settings()
    cart_total = float((cart or {}).get("total", 0.0))
    item_count = int((cart or {}).get("itemCount", 0))
    payload = {
        "id": f"vcall_{store.next_id('item')}",
        "recoveryKey": recovery_key,
        "userId": str((user or {}).get("id", "")),
        "sessionId": str(job.get("sessionId", "")),
        "cartId": str(job.get("cartId", "")),
        "status": "queued",
        "attemptCount": 0,
        "attempts": [],
        "provider": "superu",
        "providerCallId": None,
        "providerEventKeys": [],
        "providerEvents": [],
        "scriptVersion": str(settings.get("scriptVersion", "v1")),
        "campaign": {
            "itemCount": item_count,
            "cartTotal": cart_total,
            "template": str(settings.get("scriptTemplate", "")),
        },
        "outcome": "",
        "followupApplied": False,
        "estimatedCostUsd": float(settings.get("estimatedCostPerCallUsd", 0.0)),
        "createdAt": store.iso_now(),
        "updatedAt": store.iso_now(),
        "nextRetryAt": None,
        "lastError": None,
    }
    with store.lock:
        store.voice_calls_by_id[payload["id"]] = deepcopy(payload)
    return payload

def update_call_progress(store: Any, call_id: str, status: str, payload: dict[str, Any]) -> None:
    with store.lock:
        call = deepcopy(store.voice_calls_by_id.get(call_id))
    if not call:
        return
    call["status"] = status
    call["updatedAt"] = store.iso_now()
    call["providerPayload"] = payload
    with store.lock:
        store.voice_calls_by_id[call_id] = deepcopy(call)

def update_call_terminal(
    store: Any,
    call_id: str,
    status: str,
    outcome: str,
    payload: dict[str, Any],
    voice_service: Any,
) -> None:
    with store.lock:
        call = deepcopy(store.voice_calls_by_id.get(call_id))
    if not call:
        return
    call["status"] = status
    call["outcome"] = outcome
    call["providerPayload"] = payload
    call["updatedAt"] = store.iso_now()
    with store.lock:
        store.voice_calls_by_id[call_id] = deepcopy(call)
    if not bool(call.get("followupApplied", False)):
        apply_outcome_actions(
            call=call,
            voice_service=voice_service,
            support_service=voice_service.support_service,
            notification_service=voice_service.notification_service,
        )
        with store.lock:
            latest = store.voice_calls_by_id.get(call_id)
            if latest is not None:
                latest["followupApplied"] = True
                latest["updatedAt"] = store.iso_now()
                store.voice_calls_by_id[call_id] = deepcopy(latest)
