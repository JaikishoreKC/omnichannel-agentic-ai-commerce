from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.support_service import SupportService


class SupportAgent(BaseAgent):
    name = "support"

    def __init__(self, support_service: SupportService) -> None:
        self.support_service = support_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        query = str(action.params.get("query", "")).strip()
        lower = query.lower()

        if "return" in lower:
            return AgentExecutionResult(
                success=True,
                message="Most items can be returned within 30 days if unused and in original packaging.",
                data={"topic": "returns"},
                next_actions=[{"label": "Show shoes", "action": "search:running shoes"}],
            )
        if "size" in lower:
            return AgentExecutionResult(
                success=True,
                message="If you're between sizes, we usually recommend sizing up for running shoes.",
                data={"topic": "sizing"},
                next_actions=[{"label": "Find size 10 shoes", "action": "search:size_10_shoes"}],
            )
        if "human" in lower or "agent" in lower:
            ticket = self.support_service.create_ticket(
                user_id=context.user_id,
                session_id=context.session_id,
                issue=query or "User requested human escalation",
                priority="normal",
            )
            return AgentExecutionResult(
                success=True,
                message=f"I opened support ticket {ticket['id']}. A human agent will follow up soon.",
                data={"escalation": True, "ticket": ticket},
            )
        return AgentExecutionResult(
            success=True,
            message="I can help with product search, cart updates, checkout, order status, and returns questions.",
            data={"capabilities": ["search", "cart", "checkout", "order_status", "returns"]},
            next_actions=[
                {"label": "Search products", "action": "search:running shoes"},
                {"label": "Show cart", "action": "view_cart"},
            ],
        )
