from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
from app.store.in_memory import InMemoryStore


class SupportRepository:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.store = store
        self.mongo_manager = mongo_manager

    def create(self, ticket: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.support_tickets.append(deepcopy(ticket))
        self._write_to_mongo(ticket)
        return deepcopy(ticket)

    def list_open(self) -> list[dict[str, Any]]:
        with self.store.lock:
            cached = [deepcopy(ticket) for ticket in self.store.support_tickets if ticket.get("status") == "open"]
        if cached:
            return cached

        persisted = self._read_open_from_mongo()
        if persisted:
            with self.store.lock:
                existing_ids = {str(ticket.get("id", "")) for ticket in self.store.support_tickets}
                for ticket in persisted:
                    ticket_id = str(ticket.get("id", ""))
                    if ticket_id and ticket_id not in existing_ids:
                        self.store.support_tickets.append(deepcopy(ticket))
        return deepcopy(persisted)

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

    def _read_open_from_mongo(self) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({"status": "open"}).sort("createdAt", -1))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("ticketId", None)
            if isinstance(row, dict):
                output.append(row)
        return output
