from __future__ import annotations

from app.orchestrator.types import IntentResult


class AgentRouter:
    def route(self, intent: IntentResult) -> str:
        if intent.name in {"product_search"}:
            return "product"
        if intent.name in {"add_to_cart", "update_cart", "remove_from_cart", "view_cart"}:
            return "cart"
        if intent.name in {"checkout", "order_status", "cancel_order"}:
            return "order"
        return "support"

