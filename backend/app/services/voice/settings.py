from __future__ import annotations
from copy import deepcopy
from typing import Any
from app.services.voice.helpers import normalize_backoff_list

def get_settings(store: Any) -> dict[str, Any]:
    with store.lock:
        settings = deepcopy(store.voice_settings)
    return settings

def update_settings(store: Any, updates: dict[str, Any]) -> dict[str, Any]:
    with store.lock:
        current = deepcopy(store.voice_settings)
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
        store.voice_settings = merged
        return deepcopy(merged)

def ensure_defaults(store: Any, settings: Any) -> None:
    with store.lock:
        if not isinstance(store.voice_settings, dict):
            store.voice_settings = {}
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
        for key, value in default_settings.items():
            store.voice_settings.setdefault(key, value)
