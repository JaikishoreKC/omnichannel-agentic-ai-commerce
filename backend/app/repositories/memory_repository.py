from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
class MemoryRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def get(self, user_id: str) -> dict[str, Any] | None:
        cached = self._read_from_redis(user_id)
        if cached is not None:
            return deepcopy(cached)

        persisted = self._read_from_mongo(user_id)
        if persisted is not None:
            self._write_to_redis(user_id, persisted)
            return deepcopy(persisted)
        return None

    def upsert(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._write_to_redis(user_id, payload)
        self._write_to_mongo(user_id, payload)
        return deepcopy(payload)

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["memories"]

    def _redis_key(self, user_id: str) -> str:
        return f"memory:{user_id}"

    def _write_to_redis(self, user_id: str, payload: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(user_id), json.dumps(payload), ex=24 * 60 * 60)

    def _read_from_redis(self, user_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_key(user_id))
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _write_to_mongo(self, user_id: str, payload: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"userId": user_id},
            {"$set": {"userId": user_id, **deepcopy(payload)}},
            upsert=True,
        )

    def _read_from_mongo(self, user_id: str) -> dict[str, Any] | None:
        collection = self._mongo_collection()
        if collection is None:
            return None
        payload = collection.find_one({"userId": user_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("userId", None)
        return payload if isinstance(payload, dict) else None
