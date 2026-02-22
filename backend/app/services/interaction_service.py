from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.repositories.interaction_repository import InteractionRepository
from app.store.in_memory import InMemoryStore


class InteractionService:
    def __init__(
        self,
        store: InMemoryStore,
        interaction_repository: InteractionRepository,
    ) -> None:
        self.store = store
        self.interaction_repository = interaction_repository

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
        self.interaction_repository.create(payload)
        return deepcopy(payload)

    def recent(self, *, session_id: str, limit: int = 12) -> list[dict[str, Any]]:
        return self.interaction_repository.recent(session_id=session_id, limit=limit)

    def history_for_session(self, *, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.interaction_repository.list_for_session(session_id=session_id, limit=limit)

    def history_for_user(self, *, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.interaction_repository.list_for_user(user_id=user_id, limit=limit)
