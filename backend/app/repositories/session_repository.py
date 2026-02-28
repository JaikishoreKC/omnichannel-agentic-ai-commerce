from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
class SessionRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _redis_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def create(self, session: dict[str, Any]) -> dict[str, Any]:
        client = self._redis_client()
        if client:
            client.set(self._redis_key(session["id"]), json.dumps(session), ex=60 * 60)
        return deepcopy(session)

    def get(self, session_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if not client:
            return None
            
        payload = client.get(self._redis_key(session_id))
        if not payload:
            return None
            
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
            
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def update(self, session: dict[str, Any]) -> dict[str, Any]:
        return self.create(session)

    def delete(self, session_id: str) -> None:
        client = self._redis_client()
        if client:
            client.delete(self._redis_key(session_id))

    def list_all(self) -> list[dict[str, Any]]:
        client = self._redis_client()
        if not client:
            return []
        sessions = []
        for key in client.scan_iter(match="session:*"):
            payload = client.get(key)
            if not payload:
                continue
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            try:
                sessions.append(json.loads(payload))
            except json.JSONDecodeError:
                continue
        return sessions

    def find_latest_for_user(self, user_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if not client:
            return None
            
        # For Redis, finding the latest session by user is an O(N) scan.
        # In a real enterprise system, we would maintain a reverse index (Set of sessions per user_id).
        # For simplicity in this phase, we scan all active sessions.
        matching = []
        for key in client.scan_iter(match="session:*"):
            payload = client.get(key)
            if not payload:
                continue
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            try:
                session = json.loads(payload)
                if str(session.get("userId", "")) == user_id:
                    matching.append(session)
            except json.JSONDecodeError:
                continue
                
        if not matching:
            return None
            
        matching.sort(
            key=lambda session: (
                str(session.get("lastActivityAt", "")),
                str(session.get("lastActivity", "")),
                str(session.get("createdAt", "")),
            ),
            reverse=True,
        )
        return matching[0]

    def count(self) -> int:
        client = self._redis_client()
        if not client:
            return 0
        return len(list(client.scan_iter(match="session:*")))
