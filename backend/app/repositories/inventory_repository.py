from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
class InventoryRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def get(self, variant_id: str) -> dict[str, Any] | None:
        cached = self._read_from_redis(variant_id)
        if cached is not None:
            return cached

        collection = self._mongo_collection()
        if collection is None:
            return None
        payload = collection.find_one({"variantId": variant_id})
        if not payload:
            return None
        payload.pop("_id", None)
        if not isinstance(payload, dict):
            return None
        self._write_to_redis(payload)
        return payload

    def upsert(self, stock: dict[str, Any]) -> dict[str, Any]:
        self._write_to_redis(stock)
        self._write_to_mongo(stock)
        return deepcopy(stock)

    def delete(self, variant_id: str) -> None:
        self._delete_from_redis(variant_id)
        self._delete_from_mongo(variant_id)

    def list_by_product(self, product_id: str) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({"productId": product_id}).sort("variantId", 1))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            if isinstance(row, dict):
                output.append(row)
                self._write_to_redis(row)
        return output

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["inventory"]

    def _redis_key(self, variant_id: str) -> str:
        return f"inventory:{variant_id}"

    def _write_to_redis(self, stock: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(str(stock["variantId"])), json.dumps(stock), ex=60 * 60)

    def _read_from_redis(self, variant_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_key(variant_id))
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _delete_from_redis(self, variant_id: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_key(variant_id))

    def _write_to_mongo(self, stock: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"variantId": stock["variantId"]},
            {"$set": deepcopy(stock)},
            upsert=True,
        )

    def _delete_from_mongo(self, variant_id: str) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.delete_one({"variantId": variant_id})
