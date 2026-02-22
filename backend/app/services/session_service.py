from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import HTTPException

from app.store.in_memory import InMemoryStore


class SessionService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_session(
        self,
        channel: str = "web",
        initial_context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        with self.store.lock:
            session_id = self.store.next_id("session")
            now = self.store.utc_now()
            expires_at = now + timedelta(minutes=30)
            session = {
                "id": session_id,
                "userId": user_id,
                "channel": channel,
                "createdAt": now.isoformat(),
                "lastActivity": now.isoformat(),
                "expiresAt": expires_at.isoformat(),
                "context": initial_context or {},
            }
            self.store.sessions_by_id[session_id] = session
            return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self.store.lock:
            session = self.store.sessions_by_id.get(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session

    def delete_session(self, session_id: str) -> None:
        with self.store.lock:
            self.store.sessions_by_id.pop(session_id, None)

    def touch(self, session_id: str) -> None:
        with self.store.lock:
            session = self.store.sessions_by_id.get(session_id)
            if session:
                session["lastActivity"] = self.store.iso_now()

    def attach_user(self, session_id: str, user_id: str) -> None:
        with self.store.lock:
            session = self.store.sessions_by_id.get(session_id)
            if session:
                session["userId"] = user_id
                session["lastActivity"] = self.store.iso_now()

