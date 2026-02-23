from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.persistence_clients import MongoClientManager
from app.repositories.admin_activity_repository import AdminActivityRepository
from app.services.admin_activity_service import AdminActivityService
from app.store.in_memory import InMemoryStore


def _service() -> AdminActivityService:
    store = InMemoryStore()
    mongo = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=False)
    repository = AdminActivityRepository(store=store, mongo_manager=mongo)
    return AdminActivityService(
        store=store,
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
    with service.store.lock:
        service.store.admin_activity_logs[-1]["action"] = "tampered_action"

    report = service.verify_integrity(limit=100)
    assert report["ok"] is False
    assert any(issue["error"] == "entry_hash_mismatch" for issue in report["issues"])
