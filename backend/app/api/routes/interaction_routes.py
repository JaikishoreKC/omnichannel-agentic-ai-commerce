from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import HTTPException

from app.api.deps import get_optional_user
from app.container import orchestrator, session_service
from app.models.schemas import InteractionMessageRequest

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.post("/message")
async def process_message(
    payload: InteractionMessageRequest,
    user: dict[str, object] | None = Depends(get_optional_user),
) -> dict[str, object]:
    try:
        session = session_service.get_session(payload.sessionId)
    except HTTPException:
        session = session_service.create_session(channel=payload.channel, initial_context={})

    user_id = str(user["id"]) if user else session.get("userId")
    response = await orchestrator.process_message(
        message=payload.content,
        session_id=session["id"],
        user_id=str(user_id) if user_id else None,
        channel=payload.channel,
    )
    return {"type": "response", "sessionId": session["id"], "payload": response}
