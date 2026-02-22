from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import Query

from app.api.deps import get_current_user
from app.container import memory_service
from app.models.schemas import UpdatePreferencesRequest

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/preferences")
def get_preferences(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    return memory_service.get_preferences(user_id=str(user["id"]))


@router.put("/preferences")
def update_preferences(
    payload: UpdatePreferencesRequest,
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return memory_service.update_preferences(
        user_id=str(user["id"]), updates=payload.model_dump()
    )


@router.get("/history")
def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return memory_service.get_history(user_id=str(user["id"]), limit=limit)
