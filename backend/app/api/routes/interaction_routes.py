from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException

from app.api.deps import get_optional_user
from app.container import cart_service, interaction_service, memory_service, orchestrator, session_service
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
    if user_id:
        if payload.sessionId:
            cart_service.merge_guest_cart_into_user(session_id=payload.sessionId, user_id=str(user_id))
        session = session_service.resolve_user_session(
            user_id=str(user_id),
            preferred_session_id=session.get("id"),
            channel=payload.channel,
        )
    response = await orchestrator.process_message(
        message=payload.content,
        session_id=session["id"],
        user_id=str(user_id) if user_id else None,
        channel=payload.channel,
    )
    return {"type": "response", "sessionId": session["id"], "payload": response}


@router.get("/history")
def get_history(
    session_id: str | None = Query(default=None, alias="sessionId"),
    limit: int = Query(default=40, ge=1, le=200),
    user: dict[str, object] | None = Depends(get_optional_user),
) -> dict[str, object]:
    if user:
        user_id = str(user["id"])
        resolved = session_service.resolve_user_session(
            user_id=user_id,
            preferred_session_id=session_id,
            channel="web",
        )
        history = interaction_service.history_for_session(session_id=str(resolved["id"]), limit=limit)
        if not history:
            fallback = memory_service.get_history(user_id=user_id, limit=limit).get("history", [])
            synthesized = []
            for row in fallback:
                if not isinstance(row, dict):
                    continue
                summary = row.get("summary", {}) if isinstance(row.get("summary"), dict) else {}
                query = str(summary.get("query", "")).strip()
                response = str(summary.get("response", "")).strip()
                if not query and not response:
                    continue
                synthesized.append(
                    {
                        "id": f"memory_{len(synthesized)+1}",
                        "sessionId": str(resolved["id"]),
                        "userId": user_id,
                        "message": query,
                        "intent": str(row.get("type", "")),
                        "agent": "memory",
                        "response": {"message": response, "agent": "memory"},
                        "timestamp": str(row.get("timestamp", "")),
                    }
                )
            history = synthesized
        return {"sessionId": str(resolved["id"]), "messages": history}

    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required for guest history retrieval")
    session = session_service.get_session(session_id)
    history = interaction_service.history_for_session(session_id=str(session["id"]), limit=limit)
    return {"sessionId": str(session["id"]), "messages": history}
