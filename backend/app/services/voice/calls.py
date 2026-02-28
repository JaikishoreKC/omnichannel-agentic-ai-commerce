from __future__ import annotations
from copy import deepcopy
from typing import Any
from app.core.utils import generate_id, iso_now
from app.repositories.voice_repository import VoiceRepository
from app.services.voice.outcome import apply_outcome_actions

def list_calls(voice_repository: VoiceRepository, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    return voice_repository.list_calls(limit=limit, status=status)

def record_call_event(
    *,
    job: dict[str, Any],
    cart: dict[str, Any] | None,
    user: dict[str, Any] | None,
    status: str,
    error: str | None,
    voice_repository: VoiceRepository,
    voice_service: Any,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    provider_call_id: str | None = None,
    attempt_number: int | None = None,
    next_retry_at: str | None = None,
) -> None:
    call = get_or_create_call(job=job, cart=cart, user=user, voice_repository=voice_repository, voice_service=voice_service)
    attempt_index = attempt_number if attempt_number is not None else int(job.get("attempt", 0))
    event = {
        "attempt": max(1, attempt_index),
        "timestamp": iso_now(),
        "status": status,
        "error": error,
        "request": request_payload or {},
        "response": response_payload or {},
    }
    call.setdefault("attempts", []).append(event)
    call["attemptCount"] = len(call["attempts"])
    call["status"] = status
    call["updatedAt"] = iso_now()
    call["lastError"] = error
    call["nextRetryAt"] = next_retry_at
    if provider_call_id:
        call["providerCallId"] = provider_call_id
    voice_repository.upsert_call(call)

def get_or_create_call(
    *,
    job: dict[str, Any],
    cart: dict[str, Any] | None,
    user: dict[str, Any] | None,
    voice_repository: VoiceRepository,
    voice_service: Any,
) -> dict[str, Any]:
    recovery_key = str(job.get("recoveryKey", "")).strip()
    calls = voice_repository.list_calls(limit=1000) # Assuming a reasonable limit for checking existing calls
    for existing in calls:
        if str(existing.get("recoveryKey", "")) == recovery_key:
            return deepcopy(existing)

    settings = voice_service.get_settings()
    cart_total = float((cart or {}).get("total", 0.0))
    item_count = int((cart or {}).get("itemCount", 0))
    payload = {
        "id": generate_id("vcall"),
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
        "createdAt": iso_now(),
        "updatedAt": iso_now(),
        "nextRetryAt": None,
        "lastError": None,
    }
    voice_repository.upsert_call(payload)
    return payload

def update_call_progress(voice_repository: VoiceRepository, call_id: str, status: str, payload: dict[str, Any]) -> None:
    call = voice_repository.get_call(call_id)
    if not call:
        return
    call["status"] = status
    call["updatedAt"] = iso_now()
    call["providerPayload"] = payload
    voice_repository.upsert_call(call)

def update_call_terminal(
    voice_repository: VoiceRepository,
    call_id: str,
    status: str,
    outcome: str,
    payload: dict[str, Any],
    voice_service: Any,
) -> None:
    call = voice_repository.get_call(call_id)
    if not call:
        return
    call["status"] = status
    call["outcome"] = outcome
    call["providerPayload"] = payload
    call["updatedAt"] = iso_now()
    voice_repository.upsert_call(call)
    if not bool(call.get("followupApplied", False)):
        apply_outcome_actions(
            call=call,
            voice_service=voice_service,
            support_service=voice_service.support_service,
            notification_service=voice_service.notification_service,
        )
        # After applying actions, update the call to mark followup as applied
        call["followupApplied"] = True
        call["updatedAt"] = iso_now()
        voice_repository.upsert_call(call)
