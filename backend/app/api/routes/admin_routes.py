from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.container import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def stats(_: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return admin_service.stats()

