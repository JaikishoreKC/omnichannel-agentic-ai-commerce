from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.repositories.session_repository import SessionRepository
from app.store.in_memory import InMemoryStore


class SessionService:
    def __init__(self, store: InMemoryStore, session_repository: SessionRepository) -> None:
        self.store = store
        self.session_repository = session_repository
        self._expiry_minutes = 30

    def create_session(
        self,
        channel: str = "web",
        initial_context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        with self.store.lock:
            session_id = self.store.next_id("session")
            now = self.store.utc_now()
            session = {
                "id": session_id,
                "userId": user_id,
                "channel": channel,
                "createdAt": now.isoformat(),
                "lastActivity": now.isoformat(),
                "expiresAt": self._next_expiry(now=now),
                "context": {
                    "conversation": {
                        "lastIntent": None,
                        "lastAgent": None,
                        "lastMessage": None,
                        "entities": {},
                    },
                    "shopping": {"cartId": None, "viewedProducts": [], "searchHistory": []},
                    **(initial_context or {}),
                },
            }
            return self.session_repository.create(session)

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self.session_repository.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if self._is_expired(session):
            self.session_repository.delete(session_id)
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    def delete_session(self, session_id: str) -> None:
        self.session_repository.delete(session_id)

    def touch(self, session_id: str) -> None:
        session = self.session_repository.get(session_id)
        if not session:
            return
        self._mark_active(session)
        self.session_repository.update(session)

    def attach_user(self, session_id: str, user_id: str) -> None:
        session = self.session_repository.get(session_id)
        if not session:
            return
        session["userId"] = user_id
        self._mark_active(session)
        self.session_repository.update(session)

    def resolve_user_session(
        self,
        *,
        user_id: str,
        preferred_session_id: str | None,
        channel: str,
    ) -> dict[str, Any]:
        self.cleanup_expired()
        existing = self.session_repository.find_latest_for_user(user_id)
        if existing:
            expires_at = self._parse_iso(existing.get("expiresAt"))
            if expires_at is not None and expires_at <= self.store.utc_now():
                self.session_repository.delete(str(existing["id"]))
                existing = None
        if existing:
            self._mark_active(existing)
            self.session_repository.update(existing)
            return existing

        if preferred_session_id:
            preferred = self.session_repository.get(preferred_session_id)
            if preferred:
                expires_at = self._parse_iso(preferred.get("expiresAt"))
                if expires_at is not None and expires_at <= self.store.utc_now():
                    self.session_repository.delete(str(preferred["id"]))
                    preferred = None
            if preferred:
                preferred["userId"] = user_id
                self._mark_active(preferred)
                self.session_repository.update(preferred)
                return preferred

        return self.create_session(channel=channel, initial_context={}, user_id=user_id)

    def update_conversation(
        self,
        *,
        session_id: str,
        last_intent: str,
        last_agent: str,
        last_message: str,
        entities: dict[str, Any] | None = None,
    ) -> None:
        session = self.session_repository.get(session_id)
        if not session:
            return
        conversation = session.setdefault("context", {}).setdefault("conversation", {})
        conversation["lastIntent"] = last_intent
        conversation["lastAgent"] = last_agent
        conversation["lastMessage"] = last_message
        conversation["entities"] = entities or {}
        self._mark_active(session)
        self.session_repository.update(session)

    def cleanup_expired(self) -> int:
        now = self.store.utc_now()
        to_delete: list[str] = []
        with self.store.lock:
            for session_id, payload in self.store.sessions_by_id.items():
                expires_at = self._parse_iso(payload.get("expiresAt"))
                if expires_at is not None and expires_at <= now:
                    to_delete.append(session_id)
        for session_id in to_delete:
            self.session_repository.delete(session_id)
        return len(to_delete)

    @staticmethod
    def _parse_iso(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _mark_active(self, session: dict[str, Any]) -> None:
        now = self.store.utc_now()
        session["lastActivity"] = now.isoformat()
        session["expiresAt"] = self._next_expiry(now=now)

    def _next_expiry(self, *, now: datetime) -> str:
        return (now + timedelta(minutes=self._expiry_minutes)).isoformat()

    def _is_expired(self, session: dict[str, Any]) -> bool:
        expires_at = self._parse_iso(session.get("expiresAt"))
        if expires_at is None:
            return False
        return expires_at <= self.store.utc_now()
