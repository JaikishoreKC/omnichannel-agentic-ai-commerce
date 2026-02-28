import pytest
from typing import Any
from app.container import redis_manager, mongo_manager

class _FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def scan_iter(self, match: str = "*") -> Any:
        prefix = match.replace("*", "")
        for k in self.store:
            if k.startswith(prefix):
                yield k

@pytest.fixture(autouse=True)
def mock_external_clients() -> None:
    # Always mock Redis in unit tests so SessionRepository works in-memory
    redis_manager._client = _FakeRedisClient()
    # Mock Mongo if necessary, but Redis is critical for sessions now
