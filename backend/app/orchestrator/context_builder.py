from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.orchestrator.types import AgentContext, IntentResult
from app.services.cart_service import CartService
from app.services.memory_service import MemoryService
from app.services.session_service import SessionService


class ContextBuilder:
    def __init__(
        self,
        session_service: SessionService,
        cart_service: CartService,
        memory_service: MemoryService,
    ) -> None:
        self.session_service = session_service
        self.cart_service = cart_service
        self.memory_service = memory_service

    def build(
        self,
        *,
        intent: IntentResult,
        session_id: str,
        user_id: str | None,
        channel: str,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> AgentContext:
        try:
            session = self.session_service.get_session(session_id=session_id)
        except HTTPException:
            session = self.session_service.create_session(channel=channel, initial_context={})
            session_id = session["id"]

        cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
        preferences: dict[str, Any] | None = None
        memory: dict[str, Any] | None = None
        if user_id:
            memory = self.memory_service.get_memory_snapshot(user_id=user_id)
            preferences = memory.get("preferences")

        return AgentContext(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            session=session,
            cart=cart,
            preferences=preferences,
            memory=memory,
            recent_messages=recent_messages or [],
        )
