from __future__ import annotations

from app.orchestrator.types import AgentAction, IntentResult


class ActionExtractor:
    """Maps classified intents to concrete agent actions."""

    def extract(self, intent: IntentResult) -> list[AgentAction]:
        name = intent.name
        entities = intent.entities

        if name == "multi_status":
            return [
                AgentAction(name="get_cart", params={}, target_agent="cart"),
                AgentAction(name="get_order_status", params=entities, target_agent="order"),
            ]
        if name == "product_search":
            return [AgentAction(name="search_products", params=entities)]
        if name == "add_to_cart":
            return [AgentAction(name="add_item", params=entities)]
        if name == "update_cart":
            return [AgentAction(name="update_item", params=entities)]
        if name == "remove_from_cart":
            return [AgentAction(name="remove_item", params=entities)]
        if name == "view_cart":
            return [AgentAction(name="get_cart", params={})]
        if name == "checkout":
            return [AgentAction(name="checkout_summary", params={})]
        if name == "order_status":
            return [AgentAction(name="get_order_status", params=entities)]
        if name == "cancel_order":
            return [AgentAction(name="cancel_order", params=entities)]
        return [AgentAction(name="answer_question", params=entities)]
