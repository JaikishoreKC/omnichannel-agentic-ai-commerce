from __future__ import annotations
from datetime import datetime
from typing import Any
from app.core.utils import generate_id, iso_now
from app.repositories.voice_repository import VoiceRepository

def append_alert(
    *,
    code: str,
    message: str,
    severity: str,
    details: dict[str, Any] | None = None,
    voice_repository: VoiceRepository,
) -> None:
    alert = {
        "id": generate_id("valert"),
        "code": code,
        "message": message,
        "severity": severity,
        "details": details or {},
        "createdAt": iso_now(),
    }
    voice_repository.add_alert(alert)

def evaluate_alerts(
    *,
    now: datetime,
    settings: dict[str, Any],
    voice_service: Any,
) -> int:
    generated = 0
    backlog_threshold = int(settings.get("alertBacklogThreshold", 50))
    failure_ratio_threshold = float(settings.get("alertFailureRatioThreshold", 0.35))
    pending = len(voice_service.list_jobs(limit=1000, status="queued")) + len(
        voice_service.list_jobs(limit=1000, status="retrying")
    )
    if pending > backlog_threshold:
        append_alert(
            code="VOICE_BACKLOG_HIGH",
            message=f"Voice job backlog is high ({pending}).",
            severity="warning",
            details={"pendingJobs": pending},
            voice_repository=voice_service.voice_repository,
        )
        generated += 1

    today = now.date().isoformat()
    calls_today = [row for row in voice_service.list_calls(limit=2000) if str(row.get("createdAt", "")).startswith(today)]
    terminal = [
        row
        for row in calls_today
        if str(row.get("status", "")) in {"completed", "failed", "suppressed", "skipped"}
    ]
    failed = [row for row in terminal if str(row.get("status", "")) == "failed"]
    if terminal:
        ratio = len(failed) / len(terminal)
        if ratio > failure_ratio_threshold:
            ratio_val = float(ratio) # Ensure float
            append_alert(
                code="VOICE_FAILURE_RATIO_HIGH",
                message=f"Voice failure ratio today is {ratio_val:.2f}, above threshold.",
                severity="critical",
                details={"terminalCalls": len(terminal), "failedCalls": len(failed), "ratio": ratio_val},
                voice_repository=voice_service.voice_repository,
            )
            generated += 1
    return generated

def get_stats(
    *,
    now: datetime,
    settings: dict[str, Any],
    voice_service: Any,
) -> dict[str, Any]:
    today = now.date().isoformat()
    calls = voice_service.voice_repository.list_calls(limit=5000)
    jobs = voice_service.voice_repository.list_jobs(limit=5000)
    calls_today = [row for row in calls if str(row.get("createdAt", "")).startswith(today)]
    completed_today = [row for row in calls_today if str(row.get("status", "")) == "completed"]
    failed_today = [row for row in calls_today if str(row.get("status", "")) == "failed"]
    suppressed_today = [
        row for row in calls_today if str(row.get("status", "")) in {"suppressed", "skipped"}
    ]
    pending_jobs = [row for row in jobs if str(row.get("status", "")) in {"queued", "retrying"}]
    retrying_jobs = [row for row in jobs if str(row.get("status", "")) == "retrying"]
    estimated_spend = round(
        len(calls_today) * float(settings.get("estimatedCostPerCallUsd", 0.0)),
        2,
    )
    return {
        "enabled": bool(settings.get("enabled", False)),
        "totalCalls": len(calls),
        "callsToday": len(calls_today),
        "completedToday": len(completed_today),
        "failedToday": len(failed_today),
        "suppressedToday": len(suppressed_today),
        "pendingJobs": len(pending_jobs),
        "retryingJobs": len(retrying_jobs),
        "estimatedSpendToday": estimated_spend,
        "dailyBudgetUsd": float(settings.get("dailyBudgetUsd", 0.0)),
        "maxCallsPerDay": int(settings.get("maxCallsPerDay", 0)),
        "alertsOpen": len(voice_service.list_alerts(limit=200)),
    }
