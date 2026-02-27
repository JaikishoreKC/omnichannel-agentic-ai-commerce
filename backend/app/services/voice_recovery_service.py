from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.infrastructure.superu_client import SuperUClient
from app.services.notification_service import NotificationService
from app.services.support_service import SupportService
from app.store.in_memory import InMemoryStore

from app.services.voice import settings as voice_settings
from app.services.voice import jobs as voice_jobs
from app.services.voice import calls as voice_calls
from app.services.voice import alerts as voice_alerts
from app.services.voice import helpers as voice_helpers

class VoiceRecoveryService:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        settings: Settings,
        superu_client: SuperUClient,
        support_service: SupportService,
        notification_service: NotificationService,
    ) -> None:
        self.store = store
        self.settings = settings
        self.superu_client = superu_client
        self.support_service = support_service
        self.notification_service = notification_service
        voice_settings.ensure_defaults(self.store, self.settings)

    def process_due_work(self) -> dict[str, Any]:
        now = self.store.utc_now()
        settings = self.get_settings()
        enqueued = voice_jobs.enqueue_abandoned_cart_jobs(
            now=now, store=self.store, settings=settings, voice_service=self
        )
        processed = voice_jobs.process_due_jobs(
            now=now, store=self.store, voice_service=self
        )
        polled = self._poll_provider_updates(now=now)
        generated_alerts = voice_alerts.evaluate_alerts(
            now=now, settings=settings, voice_service=self
        )
        return {
            "enqueued": enqueued,
            "processed": processed,
            "polled": polled,
            "alertsGenerated": generated_alerts,
            "settingsEnabled": bool(settings.get("enabled", False)),
        }

    def get_settings(self) -> dict[str, Any]:
        return voice_settings.get_settings(self.store)

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        return voice_settings.update_settings(self.store, updates)

    def list_calls(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        return voice_calls.list_calls(self.store, limit=limit, status=status)

    def list_jobs(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self.store.lock:
            rows = list(self.store.voice_jobs_by_id.values())
        if status:
            rows = [row for row in rows if str(row.get("status", "")) == status]
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return [deepcopy(row) for row in rows[:safe_limit]]

    def suppress_user(self, *, user_id: str, reason: str) -> dict[str, Any]:
        payload = {
            "userId": user_id,
            "reason": reason.strip() or "manual_suppression",
            "createdAt": self.store.iso_now(),
        }
        with self.store.lock:
            self.store.voice_suppressions_by_user[user_id] = deepcopy(payload)
        return payload

    def unsuppress_user(self, *, user_id: str) -> None:
        with self.store.lock:
            self.store.voice_suppressions_by_user.pop(user_id, None)

    def list_suppressions(self) -> list[dict[str, Any]]:
        with self.store.lock:
            rows = list(self.store.voice_suppressions_by_user.values())
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return [deepcopy(row) for row in rows]

    def list_alerts(self, *, limit: int = 50, severity: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self.store.lock:
            rows = list(self.store.voice_alerts)
        if severity:
            rows = [row for row in rows if str(row.get("severity", "")) == severity]
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return [deepcopy(row) for row in rows[:safe_limit]]

    def stats(self) -> dict[str, Any]:
        return voice_alerts.get_stats(
            now=self.store.utc_now(),
            settings=self.get_settings(),
            store=self.store,
            voice_service=self,
        )

    def _poll_provider_updates(self, *, now: datetime) -> int:
        if not self.superu_client.enabled:
            return 0
        with self.store.lock:
            active_calls = [
                deepcopy(call)
                for call in self.store.voice_calls_by_id.values()
                if str(call.get("status", "")) in {"initiated", "ringing", "in_progress"}
                and str(call.get("providerCallId", "")).strip()
            ]
        updates = 0
        for call in active_calls:
            provider_call_id = str(call.get("providerCallId", "")).strip()
            try:
                rows = self.superu_client.fetch_call_logs(call_id=provider_call_id, limit=1)
            except RuntimeError as exc:
                voice_alerts.append_alert(
                    code="VOICE_POLL_FAILED",
                    message=f"Failed to poll SuperU call logs: {exc}",
                    severity="warning",
                    details={"callId": call.get("id"), "providerCallId": provider_call_id},
                    store=self.store,
                )
                continue
            if not rows:
                continue
            latest = rows[-1]
            normalized_status = voice_helpers.normalize_provider_status(latest)
            outcome = voice_helpers.extract_outcome(latest)
            if normalized_status in {"completed", "failed"}:
                voice_calls.update_call_terminal(
                    store=self.store,
                    call_id=str(call["id"]),
                    status=normalized_status,
                    outcome=outcome,
                    payload=latest,
                    voice_service=self,
                )
                updates += 1
            elif normalized_status in {"ringing", "in_progress"}:
                voice_calls.update_call_progress(
                    store=self.store,
                    call_id=str(call["id"]),
                    status=normalized_status,
                    payload=latest,
                )
                updates += 1
        return updates

    def ingest_provider_callback(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        provider_call_id = voice_helpers.extract_provider_call_id(payload)
        if not provider_call_id:
            return {
                "accepted": False,
                "matched": False,
                "idempotent": False,
                "reason": "missing_provider_call_id",
            }

        matched_call_id: str | None = None
        with self.store.lock:
            for call in self.store.voice_calls_by_id.values():
                if str(call.get("providerCallId", "")).strip() == provider_call_id:
                    matched_call_id = str(call.get("id", "")).strip() or None
                    break
        if not matched_call_id:
            return {
                "accepted": True,
                "matched": False,
                "idempotent": False,
                "reason": "call_not_found",
                "providerCallId": provider_call_id,
            }

        event_key = voice_helpers.provider_event_key(payload, self.superu_client)
        with self.store.lock:
            current = deepcopy(self.store.voice_calls_by_id.get(matched_call_id))
        if not isinstance(current, dict):
            return {
                "accepted": True,
                "matched": False,
                "idempotent": False,
                "reason": "call_not_found",
                "providerCallId": provider_call_id,
            }

        seen_keys = {
            str(value).strip()
            for value in current.get("providerEventKeys", [])
            if isinstance(value, str) and value.strip()
        }
        if event_key in seen_keys:
            return {
                "accepted": True,
                "matched": True,
                "idempotent": True,
                "callId": matched_call_id,
                "providerCallId": provider_call_id,
                "status": str(current.get("status", "")),
                "outcome": str(current.get("outcome", "")),
            }

        normalized_status = voice_helpers.normalize_provider_status(payload)
        outcome = voice_helpers.extract_outcome(payload)
        if normalized_status in {"completed", "failed"}:
            voice_calls.update_call_terminal(
                store=self.store,
                call_id=matched_call_id,
                status=normalized_status,
                outcome=outcome,
                payload=payload,
                voice_service=self,
            )
        else:
            voice_calls.update_call_progress(
                store=self.store,
                call_id=matched_call_id,
                status=normalized_status,
                payload=payload,
            )

        with self.store.lock:
            latest = deepcopy(self.store.voice_calls_by_id.get(matched_call_id))
            if isinstance(latest, dict):
                keys = [
                    str(value).strip()
                    for value in latest.get("providerEventKeys", [])
                    if isinstance(value, str) and value.strip()
                ]
                if event_key not in keys:
                    keys.append(event_key)
                if len(keys) > 200:
                    keys = keys[-200:]
                latest["providerEventKeys"] = keys

                events = latest.get("providerEvents", [])
                if not isinstance(events, list):
                    events = []
                events.append(
                    {
                        "key": event_key,
                        "status": normalized_status,
                        "outcome": outcome,
                        "receivedAt": self.store.iso_now(),
                    }
                )
                if len(events) > 200:
                    events = events[-200:]
                latest["providerEvents"] = events
                latest["updatedAt"] = self.store.iso_now()
                self.store.voice_calls_by_id[matched_call_id] = deepcopy(latest)

        return {
            "accepted": True,
            "matched": True,
            "idempotent": False,
            "callId": matched_call_id,
            "providerCallId": provider_call_id,
            "status": normalized_status,
            "outcome": outcome,
        }

    def _record_call_event(self, **kwargs: Any) -> None:
        voice_calls.record_call_event(store=self.store, voice_service=self, **kwargs)

    def _get_user(self, user_id: Any) -> dict[str, Any] | None:
        key = str(user_id or "").strip()
        if not key:
            return None
        with self.store.lock:
            payload = self.store.users_by_id.get(key)
            return deepcopy(payload) if payload is not None else None

    def _get_cart(self, cart_id: Any) -> dict[str, Any] | None:
        key = str(cart_id or "").strip()
        if not key:
            return None
        with self.store.lock:
            payload = self.store.carts_by_id.get(key)
            return deepcopy(payload) if payload is not None else None

    def _has_newer_order(self, *, user_id: str, since: datetime) -> bool:
        with self.store.lock:
            orders = list(self.store.orders_by_id.values())
        for order in orders:
            if str(order.get("userId", "")) != user_id:
                continue
            created_at = voice_helpers.parse_iso(order.get("createdAt"))
            if created_at and created_at > since:
                return True
        return False

    def _suppressed_users(self) -> set[str]:
        with self.store.lock:
            return {str(user_id) for user_id in self.store.voice_suppressions_by_user.keys()}
