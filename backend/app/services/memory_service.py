from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.store.in_memory import InMemoryStore


class MemoryService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        with self.store.lock:
            payload = self.store.memories_by_user_id.setdefault(
                user_id,
                {
                    "preferences": {
                        "size": None,
                        "brandPreferences": [],
                        "categories": [],
                        "priceRange": {"min": 0, "max": 0},
                    },
                    "updatedAt": self.store.iso_now(),
                },
            )
            return {"preferences": deepcopy(payload["preferences"])}

    def update_preferences(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            payload = self.store.memories_by_user_id.setdefault(
                user_id,
                {
                    "preferences": {
                        "size": None,
                        "brandPreferences": [],
                        "categories": [],
                        "priceRange": {"min": 0, "max": 0},
                    },
                    "updatedAt": self.store.iso_now(),
                },
            )
            prefs = payload["preferences"]
            for key, value in updates.items():
                if value is not None:
                    prefs[key] = value
            payload["updatedAt"] = self.store.iso_now()
            return {"success": True}

