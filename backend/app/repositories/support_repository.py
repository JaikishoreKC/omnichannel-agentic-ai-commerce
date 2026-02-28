from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
class SupportRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager

    def create(self, ticket: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(ticket)
        return deepcopy(ticket)

    def get(self, ticket_id: str) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            return None
        row = collection.find_one({"ticketId": ticket_id})
        if not row:
            return None
        row.pop("_id", None)
        row.pop("ticketId", None)
        return deepcopy(row) if isinstance(row, dict) else None

    def update(self, ticket: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(ticket)
        return deepcopy(ticket)

    def list(
        self,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        collection = self._mongo_collection()
        if collection is None:
            return []

        query: dict[str, Any] = {}
        if user_id:
            query["userId"] = user_id
        if session_id:
            query["sessionId"] = session_id
        if status:
            query["status"] = status.strip().lower()

        rows = list(collection.find(query).sort("updatedAt", -1).limit(safe_limit))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("ticketId", None)
            if isinstance(row, dict):
                output.append(row)
        return output

    def list_open(self) -> list[dict[str, Any]]:
        return self.list(status="open", limit=500)

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["support_tickets"]

    def _write_to_mongo(self, ticket: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"ticketId": ticket["id"]},
            {"$set": {"ticketId": ticket["id"], **deepcopy(ticket)}},
            upsert=True,
        )
