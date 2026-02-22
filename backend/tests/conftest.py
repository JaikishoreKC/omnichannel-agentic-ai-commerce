from __future__ import annotations

import pytest

from app.container import store
from app.store.in_memory import InMemoryStore


@pytest.fixture(autouse=True)
def reset_store_state() -> None:
    # Keep tests isolated even though the app container is module-global.
    store.import_state(InMemoryStore().export_state())
