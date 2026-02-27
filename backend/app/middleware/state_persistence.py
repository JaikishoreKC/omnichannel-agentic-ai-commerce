from __future__ import annotations
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from app.container import state_persistence, store

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

async def persist_state_on_mutation(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    if request.method in MUTATING_METHODS:
        await run_in_threadpool(state_persistence.save, store)
    return response
