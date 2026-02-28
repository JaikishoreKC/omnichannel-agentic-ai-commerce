from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any
from copy import deepcopy
from app.services.voice.helpers import parse_iso, normalize_backoff_list, extract_provider_call_id
from app.services.voice.guardrails import in_quiet_hours, next_non_quiet_time, budget_and_cap_guardrails
from app.services.voice.campaign import build_campaign_payload
from app.services.voice.alerts import append_alert

from app.core.utils import generate_id, iso_now
from app.repositories.voice_repository import VoiceRepository
from app.repositories.cart_repository import CartRepository

def enqueue_abandoned_cart_jobs(
    *,
    now: datetime,
    voice_repository: VoiceRepository,
    cart_repository: CartRepository,
    settings: dict[str, Any],
    voice_service: Any,
) -> int:
    if not bool(settings.get("enabled", False)):
        return 0
    cutoff = now - timedelta(minutes=int(settings.get("abandonmentMinutes", 30)))
    enqueued = 0
    
    carts = cart_repository.list_all()
    # existing_jobs = voice_repository.list_jobs(limit=5000)
    # Actually, we might want to check recoveryKey efficiently. 
    # For now, let's keep it simple and list all active jobs.
    active_jobs = voice_repository.list_jobs(limit=2000)
    existing_keys = {
        str(job.get("recoveryKey", ""))
        for job in active_jobs
        if str(job.get("status", ""))
        in {"queued", "retrying", "processing", "completed", "cancelled", "dead_letter"}
    }

    for cart in carts:
        user_id = str(cart.get("userId", "")).strip()
        if not user_id:
            continue
        if int(cart.get("itemCount", 0)) <= 0:
            continue
        updated_at = parse_iso(cart.get("updatedAt"))
        if updated_at is None or updated_at > cutoff:
            continue
        if voice_service._has_newer_order(user_id=user_id, since=updated_at):
            continue
        recovery_key = f"{cart['id']}::{cart['updatedAt']}"
        
        # Idempotency check
        # We can use a dedicated collection or just check voice_calls
        if recovery_key in existing_keys:
            continue
            
        job = {
            "id": generate_id("vjob"),
            "status": "queued",
            "userId": user_id,
            "sessionId": str(cart.get("sessionId", "")),
            "cartId": str(cart["id"]),
            "recoveryKey": recovery_key,
            "attempt": 0,
            "nextRunAt": now.isoformat(),
            "lastError": None,
            "createdAt": iso_now(),
            "updatedAt": iso_now(),
        }
        voice_repository.upsert_job(job)
        enqueued += 1
        existing_keys.add(recovery_key)
    return enqueued

def process_due_jobs(
    *,
    now: datetime,
    voice_repository: VoiceRepository,
    voice_service: Any,
) -> dict[str, int]:
    # We need to fetch jobs that are due
    all_jobs = voice_repository.list_jobs(limit=1000)
    due_jobs = [
        job for job in all_jobs
        if str(job.get("status", "")) in {"queued", "retrying"}
        and parse_iso(job.get("nextRunAt")) is not None
        and parse_iso(job.get("nextRunAt")) <= now
    ]
    due_jobs.sort(key=lambda row: str(row.get("nextRunAt", "")))
    
    counters = {"completed": 0, "retried": 0, "deadLetter": 0, "cancelled": 0}
    for job in due_jobs:
        result = process_single_job(job=job, now=now, voice_service=voice_service)
        counters[result] = counters.get(result, 0) + 1
    return counters

def process_single_job(
    *,
    job: dict[str, Any],
    now: datetime,
    voice_service: Any,
) -> str:
    settings = voice_service.get_settings()
    if bool(settings.get("killSwitch", False)):
        complete_job(job_id=str(job["id"]), status="cancelled", error="kill_switch", voice_repository=voice_service.voice_repository)
        append_alert(
            code="VOICE_KILL_SWITCH_ACTIVE",
            message="Voice recovery kill switch is active; jobs are being cancelled.",
            severity="warning",
            voice_repository=voice_service.voice_repository,
        )
        return "cancelled"

    user = voice_service._get_user(job.get("userId"))
    cart = voice_service._get_cart(job.get("cartId"))
    if not user or not cart or int(cart.get("itemCount", 0)) <= 0:
        complete_job(job_id=str(job["id"]), status="cancelled", error="cart_or_user_missing", voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(
            job=job,
            cart=cart,
            user=user,
            status="skipped",
            error="cart_or_user_missing",
        )
        return "cancelled"

    user_id = str(user.get("id", "")).strip()
    if user_id in voice_service._suppressed_users():
        complete_job(job_id=str(job["id"]), status="cancelled", error="suppressed_user", voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(job=job, cart=cart, user=user, status="suppressed", error="suppressed_user")
        return "cancelled"

    phone = str(user.get("phone", "")).strip()
    if not phone:
        complete_job(job_id=str(job["id"]), status="cancelled", error="missing_phone", voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(job=job, cart=cart, user=user, status="skipped", error="missing_phone")
        return "cancelled"

    if in_quiet_hours(user=user, now=now, settings=settings):
        next_run = next_non_quiet_time(user=user, now=now, settings=settings)
        reschedule_job(job_id=str(job["id"]), attempt=int(job.get("attempt", 0)), next_run=next_run, voice_repository=voice_service.voice_repository)
        return "retried"

    budget_decision = budget_and_cap_guardrails(user_id=user_id, settings=settings, now=now, voice_service=voice_service)
    if budget_decision != "ok":
        complete_job(job_id=str(job["id"]), status="cancelled", error=budget_decision, voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(job=job, cart=cart, user=user, status="skipped", error=budget_decision)
        append_alert(
            code="VOICE_GUARDRAIL_TRIGGERED",
            message=f"Voice call blocked by guardrail: {budget_decision}",
            severity="warning",
            details={"userId": user_id, "jobId": str(job["id"])},
            voice_repository=voice_service.voice_repository,
        )
        return "cancelled"

    campaign = build_campaign_payload(user=user, cart=cart, settings=settings, default_template=voice_service.settings.voice_script_template)
    assistant_id = str(settings.get("assistantId", "")).strip() or None
    from_phone_number = str(settings.get("fromPhoneNumber", "")).strip() or None
    attempt_number = int(job.get("attempt", 0)) + 1

    if not voice_service.superu_client.enabled:
        complete_job(job_id=str(job["id"]), status="cancelled", error="provider_not_configured", voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(
            job=job,
            cart=cart,
            user=user,
            status="skipped",
            error="provider_not_configured",
            request_payload=campaign,
        )
        append_alert(
            code="VOICE_PROVIDER_NOT_CONFIGURED",
            message="Voice recovery is enabled but SuperU credentials are missing.",
            severity="critical",
            voice_repository=voice_service.voice_repository,
        )
        return "cancelled"
    if not assistant_id or not from_phone_number:
        complete_job(job_id=str(job["id"]), status="cancelled", error="provider_not_configured", voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(
            job=job,
            cart=cart,
            user=user,
            status="skipped",
            error="provider_not_configured",
            request_payload=campaign,
        )
        append_alert(
            code="VOICE_PROVIDER_NOT_CONFIGURED",
            message="Voice settings require assistantId and fromPhoneNumber.",
            severity="critical",
            voice_repository=voice_service.voice_repository,
        )
        return "cancelled"

    try:
        response = voice_service.superu_client.start_outbound_call(
            to_phone_number=phone,
            assistant_id=assistant_id,
            from_phone_number=from_phone_number,
            metadata={
                "campaign": campaign,
                "jobId": str(job.get("id", "")),
                "cartId": str(cart.get("id", "")),
                "userId": user_id,
            },
        )
        provider_call_id = extract_provider_call_id(response)
        complete_job(job_id=str(job["id"]), status="completed", error=None, voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(
            job=job,
            cart=cart,
            user=user,
            status="initiated",
            error=None,
            request_payload=campaign,
            response_payload=response,
            provider_call_id=provider_call_id,
            attempt_number=attempt_number,
        )
        # Idempotency is handled by checking existing_keys in enqueue_abandoned_cart_jobs
        return "completed"
    except RuntimeError as exc:
        error = str(exc)
        max_attempts = max(1, int(settings.get("maxAttemptsPerCart", 3)))
        if attempt_number >= max_attempts:
            complete_job(job_id=str(job["id"]), status="dead_letter", error=error, voice_repository=voice_service.voice_repository)
            voice_service._record_call_event(
                job=job,
                cart=cart,
                user=user,
                status="failed",
                error=error,
                request_payload=campaign,
                attempt_number=attempt_number,
            )
            append_alert(
                code="VOICE_DEAD_LETTER",
                message="Voice call job moved to dead-letter after max retries.",
                severity="critical",
                details={"jobId": str(job["id"]), "error": error},
                voice_repository=voice_service.voice_repository,
            )
            return "deadLetter"

        backoffs = normalize_backoff_list(settings.get("retryBackoffSeconds"))
        delay = backoffs[min(attempt_number - 1, len(backoffs) - 1)]
        next_run = now + timedelta(seconds=delay)
        reschedule_job(job_id=str(job["id"]), attempt=attempt_number, next_run=next_run, error=error, voice_repository=voice_service.voice_repository)
        voice_service._record_call_event(
            job=job,
            cart=cart,
            user=user,
            status="retrying",
            error=error,
            request_payload=campaign,
            attempt_number=attempt_number,
            next_retry_at=next_run.isoformat(),
        )
        return "retried"

def reschedule_job(
    *,
    job_id: str,
    attempt: int,
    next_run: datetime,
    voice_repository: VoiceRepository,
    error: str | None = None,
) -> None:
    current = voice_repository.get_job(job_id)
    if current is None:
        return
    updated = deepcopy(current)
    updated["status"] = "retrying"
    updated["attempt"] = max(0, int(attempt))
    updated["nextRunAt"] = next_run.isoformat()
    updated["lastError"] = error
    updated["updatedAt"] = iso_now()
    voice_repository.upsert_job(updated)

def complete_job(*, job_id: str, status: str, error: str | None, voice_repository: VoiceRepository) -> None:
    current = voice_repository.get_job(job_id)
    if current is None:
        return
    updated = deepcopy(current)
    updated["status"] = status
    updated["lastError"] = error
    updated["updatedAt"] = iso_now()
    if status in {"completed", "cancelled", "dead_letter"}:
        updated["nextRunAt"] = None
    voice_repository.upsert_job(updated)
