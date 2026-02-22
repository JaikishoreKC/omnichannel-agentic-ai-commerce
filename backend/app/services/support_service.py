from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.repositories.support_repository import SupportRepository
from app.store.in_memory import InMemoryStore


class SupportService:
    def __init__(
        self,
        store: InMemoryStore,
        support_repository: SupportRepository,
    ) -> None:
        self.store = store
        self.support_repository = support_repository

    def create_ticket(
        self,
        *,
        user_id: str | None,
        session_id: str,
        issue: str,
        priority: str = "normal",
    ) -> dict[str, Any]:
        ticket = {
            "id": f"ticket_{self.store.next_id('item')}",
            "userId": user_id,
            "sessionId": session_id,
            "issue": issue.strip(),
            "priority": priority,
            "status": "open",
            "createdAt": self.store.iso_now(),
            "updatedAt": self.store.iso_now(),
        }
        self.support_repository.create(ticket)
        return deepcopy(ticket)
