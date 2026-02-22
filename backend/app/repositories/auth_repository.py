from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class AuthRepository:
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

    def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.users_by_id[user["id"]] = deepcopy(user)
            self.store.user_ids_by_email[str(user["email"]).strip().lower()] = user["id"]
        self._write_user_through(user)
        return deepcopy(user)

    def update_user(self, user: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.users_by_id[user["id"]] = deepcopy(user)
            self.store.user_ids_by_email[str(user["email"]).strip().lower()] = user["id"]
        self._write_user_through(user)
        return deepcopy(user)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            user = self.store.users_by_id.get(user_id)
            if user is not None:
                return deepcopy(user)

        cached = self._read_user_from_redis_by_id(user_id)
        if cached is not None:
            self._cache_user_in_store(cached)
            return deepcopy(cached)

        persisted = self._read_user_from_mongo_by_id(user_id)
        if persisted is not None:
            self._cache_user_in_store(persisted)
            self._write_user_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized = email.strip().lower()
        with self.store.lock:
            user_id = self.store.user_ids_by_email.get(normalized)
            if user_id:
                user = self.store.users_by_id.get(user_id)
                if user is not None:
                    return deepcopy(user)

        cached = self._read_user_from_redis_by_email(normalized)
        if cached is not None:
            self._cache_user_in_store(cached)
            return deepcopy(cached)

        persisted = self._read_user_from_mongo_by_email(normalized)
        if persisted is not None:
            self._cache_user_in_store(persisted)
            self._write_user_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def set_refresh_token(self, token: str, payload: dict[str, Any]) -> None:
        with self.store.lock:
            self.store.refresh_tokens[token] = deepcopy(payload)
        self._write_refresh_to_redis(token, payload)
        self._write_refresh_to_mongo(token, payload)

    def get_refresh_token(self, token: str) -> dict[str, Any] | None:
        with self.store.lock:
            payload = self.store.refresh_tokens.get(token)
            if payload is not None:
                return deepcopy(payload)

        cached = self._read_refresh_from_redis(token)
        if cached is not None:
            with self.store.lock:
                self.store.refresh_tokens[token] = deepcopy(cached)
            return deepcopy(cached)

        persisted = self._read_refresh_from_mongo(token)
        if persisted is not None:
            with self.store.lock:
                self.store.refresh_tokens[token] = deepcopy(persisted)
            self._write_refresh_to_redis(token, persisted)
            return deepcopy(persisted)
        return None

    def revoke_refresh_token(self, token: str) -> None:
        with self.store.lock:
            self.store.refresh_tokens.pop(token, None)
        self._delete_refresh_from_redis(token)
        self._delete_refresh_from_mongo(token)

    def _cache_user_in_store(self, user: dict[str, Any]) -> None:
        user_id = str(user.get("id", ""))
        email = str(user.get("email", "")).strip().lower()
        if not user_id or not email:
            return
        with self.store.lock:
            self.store.users_by_id[user_id] = deepcopy(user)
            self.store.user_ids_by_email[email] = user_id

    def _write_user_through(self, user: dict[str, Any]) -> None:
        self._write_user_to_redis(user)
        self._write_user_to_mongo(user)

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_users_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["users"]

    def _mongo_refresh_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["refresh_tokens"]

    def _redis_user_id_key(self, user_id: str) -> str:
        return f"user:id:{user_id}"

    def _redis_user_email_key(self, email: str) -> str:
        return f"user:email:{email}"

    def _redis_refresh_key(self, token: str) -> str:
        return f"refresh:{token}"

    def _write_user_to_redis(self, user: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        payload = json.dumps(user)
        user_id = str(user.get("id", ""))
        email = str(user.get("email", "")).strip().lower()
        if not user_id or not email:
            return
        client.set(self._redis_user_id_key(user_id), payload, ex=60 * 60)
        client.set(self._redis_user_email_key(email), payload, ex=60 * 60)

    def _read_user_from_redis_by_id(self, user_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_user_id_key(user_id))
        return self._decode_dict_payload(payload)

    def _read_user_from_redis_by_email(self, email: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_user_email_key(email))
        return self._decode_dict_payload(payload)

    def _write_user_to_mongo(self, user: dict[str, Any]) -> None:
        collection = self._mongo_users_collection()
        if collection is None:
            return
        collection.update_one(
            {"userId": user["id"]},
            {"$set": {"userId": user["id"], **deepcopy(user)}},
            upsert=True,
        )

    def _read_user_from_mongo_by_id(self, user_id: str) -> dict[str, Any] | None:
        collection = self._mongo_users_collection()
        if collection is None:
            return None
        payload = collection.find_one({"userId": user_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("userId", None)
        return payload if isinstance(payload, dict) else None

    def _read_user_from_mongo_by_email(self, email: str) -> dict[str, Any] | None:
        collection = self._mongo_users_collection()
        if collection is None:
            return None
        payload = collection.find_one({"email": email})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("userId", None)
        return payload if isinstance(payload, dict) else None

    def _write_refresh_to_redis(self, token: str, payload: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_refresh_key(token), json.dumps(payload), ex=7 * 24 * 60 * 60)

    def _read_refresh_from_redis(self, token: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_refresh_key(token))
        return self._decode_dict_payload(payload)

    def _delete_refresh_from_redis(self, token: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_refresh_key(token))

    def _write_refresh_to_mongo(self, token: str, payload: dict[str, Any]) -> None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return
        collection.update_one(
            {"token": token},
            {"$set": {"token": token, **deepcopy(payload)}},
            upsert=True,
        )

    def _read_refresh_from_mongo(self, token: str) -> dict[str, Any] | None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return None
        payload = collection.find_one({"token": token})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("token", None)
        return payload if isinstance(payload, dict) else None

    def _delete_refresh_from_mongo(self, token: str) -> None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return
        collection.delete_one({"token": token})

    @staticmethod
    def _decode_dict_payload(payload: Any) -> dict[str, Any] | None:
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
