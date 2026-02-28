from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
class OrderRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager

    def create(self, order: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(order)
        return deepcopy(order)

    def update(self, order: dict[str, Any]) -> dict[str, Any]:
        self._write_to_mongo(order)
        return deepcopy(order)

    def get(self, order_id: str) -> dict[str, Any] | None:
        collection = self._orders_collection()
        if collection is None:
            return None
        payload = collection.find_one({"orderId": order_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("orderId", None)
        return deepcopy(payload)

    def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        collection = self._orders_collection()
        if collection is None:
            return []
        payloads = list(collection.find({"userId": user_id}).sort("createdAt", -1))
        orders: list[dict[str, Any]] = []
        for payload in payloads:
            payload.pop("_id", None)
            payload.pop("orderId", None)
            if isinstance(payload, dict):
                orders.append(payload)
        return orders

    def list_all(self) -> list[dict[str, Any]]:
        collection = self._orders_collection()
        if collection is None:
            return []
        payloads = list(collection.find({}).sort("createdAt", -1))
        orders: list[dict[str, Any]] = []
        for payload in payloads:
            payload.pop("_id", None)
            payload.pop("orderId", None)
            if isinstance(payload, dict):
                orders.append(payload)
        return orders

    def get_idempotent(self, key: str) -> str | None:
        collection = self._idempotency_collection()
        if collection is None:
            return None
        payload = collection.find_one({"key": key})
        if not payload:
            return None
        return str(payload.get("orderId", ""))

    def set_idempotent(self, *, key: str, order_id: str) -> None:
        collection = self._idempotency_collection()
        if collection is None:
            return
        collection.update_one(
            {"key": key},
            {"$set": {"key": key, "orderId": order_id}},
            upsert=True,
        )

    def _orders_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["orders"]

    def _idempotency_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["idempotency_keys"]

    def _write_to_mongo(self, order: dict[str, Any]) -> None:
        collection = self._orders_collection()
        if collection is None:
            return
        collection.update_one(
            {"orderId": order["id"]},
            {"$set": {"orderId": order["id"], **deepcopy(order)}},
            upsert=True,
        )
