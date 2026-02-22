from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class InteractionRepository:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.store = store
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get("sessionId", ""))
        if not session_id:
            raise ValueError("Interaction payload requires sessionId")

        with self.store.lock:
            self.store.messages_by_session.setdefault(session_id, []).append(deepcopy(payload))
        self._append_to_redis(session_id, payload)
        self._write_to_mongo(payload)
        return deepcopy(payload)

    def recent(self, *, session_id: str, limit: int = 12) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self.store.lock:
            items = self.store.messages_by_session.get(session_id, [])
            if items:
                return deepcopy(items[-safe_limit:])

        cached = self._read_session_from_redis(session_id)
        if cached:
            with self.store.lock:
                self.store.messages_by_session[session_id] = deepcopy(cached)
            return deepcopy(cached[-safe_limit:])

        persisted = self._read_session_from_mongo(session_id)
        if persisted:
            with self.store.lock:
                self.store.messages_by_session[session_id] = deepcopy(persisted)
            self._write_session_to_redis(session_id, persisted)
            return deepcopy(persisted[-safe_limit:])
        return []

    def list_for_session(self, *, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.recent(session_id=session_id, limit=limit)

    def list_for_user(self, *, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self.store.lock:
            cached = [
                deepcopy(record)
                for rows in self.store.messages_by_session.values()
                for record in rows
                if str(record.get("userId", "")) == user_id
            ]
        if cached:
            cached.sort(key=lambda item: str(item.get("timestamp", "")))
            return deepcopy(cached[-safe_limit:])

        persisted = self._read_user_from_mongo(user_id)
        if persisted:
            with self.store.lock:
                for row in persisted:
                    session_id = str(row.get("sessionId", "")).strip()
                    if not session_id:
                        continue
                    self.store.messages_by_session.setdefault(session_id, []).append(deepcopy(row))
            return deepcopy(persisted[-safe_limit:])
        return []

    def list_by_date(self, *, date_prefix: str) -> list[dict[str, Any]]:
        with self.store.lock:
            cached = [
                deepcopy(record)
                for rows in self.store.messages_by_session.values()
                for record in rows
                if str(record.get("timestamp", "")).startswith(date_prefix)
            ]
        if cached:
            return cached

        persisted = self._read_by_date_from_mongo(date_prefix)
        if persisted:
            with self.store.lock:
                for row in persisted:
                    session_id = str(row.get("sessionId", ""))
                    if not session_id:
                        continue
                    self.store.messages_by_session.setdefault(session_id, []).append(deepcopy(row))
            return deepcopy(persisted)
        return []

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["interactions"]

    def _redis_key(self, session_id: str) -> str:
        return f"interaction:session:{session_id}"

    def _append_to_redis(self, session_id: str, payload: dict[str, Any]) -> None:
        entries = self._read_session_from_redis(session_id)
        entries.append(deepcopy(payload))
        if len(entries) > 500:
            entries = entries[-500:]
        self._write_session_to_redis(session_id, entries)

    def _write_session_to_redis(self, session_id: str, entries: list[dict[str, Any]]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(session_id), json.dumps(entries), ex=24 * 60 * 60)

    def _read_session_from_redis(self, session_id: str) -> list[dict[str, Any]]:
        client = self._redis_client()
        if client is None:
            return []
        payload = client.get(self._redis_key(session_id))
        if not payload:
            return []
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if not isinstance(decoded, list):
            return []
        return [item for item in decoded if isinstance(item, dict)]

    def _write_to_mongo(self, payload: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"messageId": payload["id"]},
            {"$set": {"messageId": payload["id"], **deepcopy(payload)}},
            upsert=True,
        )

    def _read_session_from_mongo(self, session_id: str) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({"sessionId": session_id}).sort("timestamp", 1))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("messageId", None)
            if isinstance(row, dict):
                output.append(row)
        return output

    def _read_by_date_from_mongo(self, date_prefix: str) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({"timestamp": {"$regex": f"^{date_prefix}"}}).sort("timestamp", 1))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("messageId", None)
            if isinstance(row, dict):
                output.append(row)
        return output

    def _read_user_from_mongo(self, user_id: str) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({"userId": user_id}).sort("timestamp", 1))
        output: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("messageId", None)
            if isinstance(row, dict):
                output.append(row)
        return output
