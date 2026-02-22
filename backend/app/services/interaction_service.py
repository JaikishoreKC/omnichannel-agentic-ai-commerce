from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.store.in_memory import InMemoryStore


class InteractionService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def record(
        self,
        *,
        session_id: str,
        user_id: str | None,
        message: str,
        intent: str,
        agent: str,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        with self.store.lock:
            payload = {
                "id": f"msg_{self.store.next_id('item')}",
                "sessionId": session_id,
                "userId": user_id,
                "message": message,
                "intent": intent,
                "agent": agent,
                "response": response,
                "timestamp": self.store.iso_now(),
            }
            self.store.messages_by_session.setdefault(session_id, []).append(payload)
            return deepcopy(payload)

    def recent(self, *, session_id: str, limit: int = 12) -> list[dict[str, Any]]:
        with self.store.lock:
            items = self.store.messages_by_session.get(session_id, [])
            return deepcopy(items[-limit:])

