from __future__ import annotations

from fastapi import APIRouter, Response

from app.container import session_service
from app.models.schemas import CreateSessionRequest

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201)
def create_session(payload: CreateSessionRequest) -> dict[str, object]:
    session = session_service.create_session(
        channel=payload.channel,
        initial_context=payload.initialContext,
    )
    return {"sessionId": session["id"], "expiresAt": session["expiresAt"]}


@router.get("/{session_id}")
def get_session(session_id: str) -> dict[str, object]:
    return session_service.get_session(session_id=session_id)


@router.delete("/{session_id}", status_code=204, response_class=Response)
def delete_session(session_id: str) -> Response:
    session_service.delete_session(session_id=session_id)
    return Response(status_code=204)
