from __future__ import annotations

from typing import Any
from app.core.config import Settings
from app.infrastructure.persistence_clients import MongoClientManager
from app.repositories.admin_activity_repository import AdminActivityRepository
from app.services.admin_activity_service import AdminActivityService
from app.store.in_memory import InMemoryStore


class _FakeMongoCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
    def find(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> Any:
        from copy import deepcopy
        results = [deepcopy(doc) for doc in self.docs]
        class FakeCursor(list):
            def sort(self, *args, **kwargs):
                if args:
                    field, direction = args[0] if isinstance(args[0], tuple) else (args[0], args[1])
                    super().sort(key=lambda x: x.get(str(field)), reverse=(direction == -1))
                return self
        return FakeCursor(results)
    def insert_one(self, doc: dict[str, Any]) -> Any:
        self.docs.append(doc)
    def count_documents(self, filter: dict[str, Any]) -> int:
        return len(self.docs)

class _FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeMongoCollection] = {}
    def __getitem__(self, name: str) -> _FakeMongoCollection:
        if name not in self.collections:
            self.collections[name] = _FakeMongoCollection()
        return self.collections[name]

class _FakeMongoClient:
    def get_default_database(self) -> _FakeDatabase:
        return _FakeDatabase()

def _service() -> AdminActivityService:
    mongo = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=True)
    mongo._client = _FakeMongoClient()
    repository = AdminActivityRepository(mongo_manager=mongo)
    return AdminActivityService(
        settings=Settings(token_secret="test-admin-log-secret"),
        admin_activity_repository=repository,
    )


def test_admin_activity_hash_chain_and_integrity() -> None:
    service = _service()
    admin_user = {"id": "user_000001", "email": "admin@example.com"}

    first = service.record(
        admin_user=admin_user,
        action="category_create",
        resource="category",
        resource_id="cat_001",
        before=None,
        after={"id": "cat_001", "name": "Shoes"},
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    second = service.record(
        admin_user=admin_user,
        action="category_update",
        resource="category",
        resource_id="cat_001",
        before={"id": "cat_001", "name": "Shoes"},
        after={"id": "cat_001", "name": "Running Shoes"},
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert first["entryHash"]
    assert second["entryHash"]
    assert second["prevHash"] == first["entryHash"]

    report = service.verify_integrity(limit=100)
    assert report["ok"] is True
    assert report["total"] == 2
    assert report["issues"] == []


def test_admin_activity_integrity_detects_tampering() -> None:
    service = _service()
    admin_user = {"id": "user_000001", "email": "admin@example.com"}
    service.record(
        admin_user=admin_user,
        action="product_create",
        resource="product",
        resource_id="prod_123",
        before=None,
        after={"id": "prod_123", "name": "Training Backpack"},
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    
    # Tamper with the data in the fake mongo collection
    docs = service.admin_activity_repository.mongo_manager.client.get_default_database()["admin_activity_logs"].docs
    docs[-1]["action"] = "tampered_action"

    report = service.verify_integrity(limit=100)
    assert report["ok"] is False
    assert any(issue["error"] == "entry_hash_mismatch" for issue in report["issues"])
