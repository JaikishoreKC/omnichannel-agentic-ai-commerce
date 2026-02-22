from __future__ import annotations

from fastapi import APIRouter, Request

from app.container import auth_service, cart_service, session_service
from app.models.schemas import LoginRequest, RefreshRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request) -> dict[str, object]:
    result = auth_service.register(
        email=payload.email,
        password=payload.password,
        name=payload.name,
    )
    session_id = request.headers.get("X-Session-Id") or request.cookies.get("session_id")
    if session_id:
        cart_service.attach_cart_to_user(session_id=session_id, user_id=result["user"]["id"])
        session_service.attach_user(session_id=session_id, user_id=result["user"]["id"])
    return result


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> dict[str, object]:
    result = auth_service.login(email=payload.email, password=payload.password)
    session_id = request.headers.get("X-Session-Id") or request.cookies.get("session_id")
    if session_id:
        cart_service.attach_cart_to_user(session_id=session_id, user_id=result["user"]["id"])
        session_service.attach_user(session_id=session_id, user_id=result["user"]["id"])
    return result


@router.post("/refresh")
def refresh(payload: RefreshRequest) -> dict[str, object]:
    return auth_service.refresh(refresh_token=payload.refreshToken)
