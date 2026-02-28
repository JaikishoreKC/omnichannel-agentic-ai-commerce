from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager

class VoiceRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager

    def get_settings(self) -> dict[str, Any] | None:
        collection = self._mongo_db()["voice_settings"]
        row = collection.find_one({"id": "global_settings"})
        if row:
            row.pop("_id", None)
            row.pop("id", None)
            return row
        return None

    def upsert_settings(self, settings: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_settings"]
        collection.update_one(
            {"id": "global_settings"},
            {"$set": deepcopy(settings)},
            upsert=True,
        )

    def upsert_job(self, job: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_jobs"]
        collection.update_one(
            {"id": job["id"]},
            {"$set": deepcopy(job)},
            upsert=True,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        collection = self._mongo_db()["voice_jobs"]
        row = collection.find_one({"id": job_id})
        if row:
            row.pop("_id", None)
            return row
        return None

    def list_jobs(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        collection = self._mongo_db()["voice_jobs"]
        query = {}
        if status:
            query["status"] = status
        rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
        for row in rows:
            row.pop("_id", None)
        return rows

    def upsert_call(self, call: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_calls"]
        collection.update_one(
            {"id": call["id"]},
            {"$set": deepcopy(call)},
            upsert=True,
        )

    def get_call(self, call_id: str) -> dict[str, Any] | None:
        collection = self._mongo_db()["voice_calls"]
        row = collection.find_one({"id": call_id})
        if row:
            row.pop("_id", None)
            return row
        return None

    def find_call_by_provider_id(self, provider_call_id: str) -> dict[str, Any] | None:
        collection = self._mongo_db()["voice_calls"]
        row = collection.find_one({"providerCallId": provider_call_id})
        if row:
            row.pop("_id", None)
            return row
        return None

    def list_calls(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        collection = self._mongo_db()["voice_calls"]
        query = {}
        if status:
            query["status"] = status
        rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
        for row in rows:
            row.pop("_id", None)
        return rows

    def add_alert(self, alert: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_alerts"]
        collection.insert_one(deepcopy(alert))

    def list_alerts(self, *, severity: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        collection = self._mongo_db()["voice_alerts"]
        query = {}
        if severity:
            query["severity"] = severity
        rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
        for row in rows:
            row.pop("_id", None)
        return rows

    def upsert_suppression(self, user_id: str, payload: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_suppressions"]
        collection.update_one(
            {"userId": user_id},
            {"$set": deepcopy(payload)},
            upsert=True,
        )

    def delete_suppression(self, user_id: str) -> None:
        collection = self._mongo_db()["voice_suppressions"]
        collection.delete_one({"userId": user_id})

    def list_suppressions(self) -> list[dict[str, Any]]:
        collection = self._mongo_db()["voice_suppressions"]
        rows = list(collection.find({}).sort("createdAt", -1))
        for row in rows:
            row.pop("_id", None)
        return rows

    def is_suppressed(self, user_id: str) -> bool:
        collection = self._mongo_db()["voice_suppressions"]
        return collection.find_one({"userId": user_id}) is not None

    def get_suppressed_user_ids(self) -> set[str]:
        collection = self._mongo_db()["voice_suppressions"]
        rows = list(collection.find({}, {"userId": 1}))
        return {str(row["userId"]) for row in rows}

    def _mongo_db(self) -> Any:
        client = self.mongo_manager.client
        if client is None:
            raise RuntimeError("Mongo client not connected")
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database
