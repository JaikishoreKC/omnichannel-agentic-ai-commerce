from __future__ import annotations
from copy import deepcopy
from typing import Any
from app.services.voice.helpers import normalize_backoff_list
from app.repositories.voice_repository import VoiceRepository

def get_settings(voice_repository: VoiceRepository) -> dict[str, Any]:
    settings = voice_repository.get_settings()
    return settings or {}

def update_settings(voice_repository: VoiceRepository, updates: dict[str, Any]) -> dict[str, Any]:
    current = voice_repository.get_settings() or {}
    merged = {**current, **updates}
    merged["abandonmentMinutes"] = max(1, int(merged.get("abandonmentMinutes", 30)))
    merged["maxAttemptsPerCart"] = max(1, int(merged.get("maxAttemptsPerCart", 3)))
    merged["maxCallsPerUserPerDay"] = max(1, int(merged.get("maxCallsPerUserPerDay", 2)))
    merged["maxCallsPerDay"] = max(1, int(merged.get("maxCallsPerDay", 300)))
    merged["dailyBudgetUsd"] = max(0.0, float(merged.get("dailyBudgetUsd", 300.0)))
    merged["estimatedCostPerCallUsd"] = max(
        0.0, float(merged.get("estimatedCostPerCallUsd", 0.7))
    )
    merged["quietHoursStart"] = max(0, min(23, int(merged.get("quietHoursStart", 21))))
    merged["quietHoursEnd"] = max(0, min(23, int(merged.get("quietHoursEnd", 8))))
    merged["retryBackoffSeconds"] = normalize_backoff_list(
        merged.get("retryBackoffSeconds")
    )
    merged["scriptVersion"] = str(merged.get("scriptVersion", "v1")).strip() or "v1"
    # scriptTemplate should be handled by the service to use its default if missing
    merged["assistantId"] = str(merged.get("assistantId", "")).strip()
    merged["fromPhoneNumber"] = str(merged.get("fromPhoneNumber", "")).strip()
    merged["defaultTimezone"] = str(merged.get("defaultTimezone", "UTC")).strip() or "UTC"
    merged["alertBacklogThreshold"] = max(
        1, int(merged.get("alertBacklogThreshold", 50))
    )
    merged["alertFailureRatioThreshold"] = max(
        0.01, min(1.0, float(merged.get("alertFailureRatioThreshold", 0.35)))
    )
    merged["enabled"] = bool(merged.get("enabled", False))
    merged["killSwitch"] = bool(merged.get("killSwitch", False))
    voice_repository.upsert_settings(merged)
    return merged

def ensure_defaults(voice_repository: VoiceRepository, settings: Any) -> None:
    current = voice_repository.get_settings()
    if current is None:
        current = {}
    
    default_settings = {
        "enabled": bool(settings.superu_enabled),
        "killSwitch": bool(settings.voice_global_kill_switch),
        "abandonmentMinutes": int(settings.voice_abandonment_minutes),
        "maxAttemptsPerCart": int(settings.voice_max_attempts_per_cart),
        "maxCallsPerUserPerDay": int(settings.voice_max_calls_per_user_per_day),
        "maxCallsPerDay": int(settings.voice_max_calls_per_day),
        "dailyBudgetUsd": float(settings.voice_daily_budget_usd),
        "estimatedCostPerCallUsd": float(settings.voice_estimated_cost_per_call_usd),
        "quietHoursStart": int(settings.voice_quiet_hours_start),
        "quietHoursEnd": int(settings.voice_quiet_hours_end),
        "retryBackoffSeconds": normalize_backoff_list(
            settings.voice_retry_backoff_seconds_csv
        ),
        "scriptVersion": settings.voice_script_version,
        "scriptTemplate": settings.voice_script_template,
        "assistantId": settings.superu_assistant_id,
        "fromPhoneNumber": settings.superu_from_phone_number,
        "defaultTimezone": settings.voice_default_timezone,
        "alertBacklogThreshold": int(settings.voice_alert_backlog_threshold),
        "alertFailureRatioThreshold": float(settings.voice_alert_failure_ratio_threshold),
    }
    
    changed = False
    for key, value in default_settings.items():
        if key not in current:
            current[key] = value
            changed = True
            
    if changed:
        voice_repository.upsert_settings(current)
