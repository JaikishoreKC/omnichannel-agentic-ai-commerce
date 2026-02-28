from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
class NotificationRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(payload)
        return deepcopy(payload)

    def list_for_user(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({"userId": user_id}).sort("createdAt", -1).limit(safe_limit))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            if isinstance(row, dict):
                output.append(row)
        return output

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["notifications"]

    def _write_to_mongo(self, payload: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"notificationId": payload["id"]},
            {"$set": {"notificationId": payload["id"], **deepcopy(payload)}},
            upsert=True,
        )
