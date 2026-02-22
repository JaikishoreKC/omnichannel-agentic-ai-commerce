from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.cart_service import CartService


class CartAgent(BaseAgent):
    name = "cart"

    def __init__(self, cart_service: CartService) -> None:
        self.cart_service = cart_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = context.user_id
        session_id = context.session_id
        params = action.params

        if action.name == "get_cart":
            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            return AgentExecutionResult(
                success=True,
                message=f"Your cart has {cart['itemCount']} item(s), total ${cart['total']:.2f}.",
                data={"cart": cart},
                next_actions=self._cart_next_actions(cart),
            )

        if action.name == "add_item":
            product_id = params.get("productId")
            variant_id = params.get("variantId")
            if not product_id or not variant_id:
                inferred = self._infer_from_recent(context.recent_messages)
                product_id = product_id or inferred.get("productId")
                variant_id = variant_id or inferred.get("variantId")
            if not product_id or not variant_id:
                return AgentExecutionResult(
                    success=False,
                    message="Tell me which product to add, or pick one from recommendations.",
                    data={},
                )

            quantity = int(params.get("quantity", 1))
            cart = self.cart_service.add_item(
                user_id=user_id,
                session_id=session_id,
                product_id=str(product_id),
                variant_id=str(variant_id),
                quantity=quantity,
            )
            return AgentExecutionResult(
                success=True,
                message=f"Added item to cart. New total is ${cart['total']:.2f}.",
                data={"cart": cart},
                next_actions=self._cart_next_actions(cart),
            )

        if action.name == "update_item":
            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            item_id = params.get("itemId")
            if not item_id and cart["items"]:
                item_id = cart["items"][0]["itemId"]
            if not item_id:
                return AgentExecutionResult(
                    success=False,
                    message="Your cart is empty. Add an item first.",
                    data={"cart": cart},
                )

            quantity = int(params.get("quantity", 1))
            updated = self.cart_service.update_item(
                user_id=user_id,
                session_id=session_id,
                item_id=str(item_id),
                quantity=quantity,
            )
            return AgentExecutionResult(
                success=True,
                message=f"Updated cart item quantity. Total is now ${updated['total']:.2f}.",
                data={"cart": updated},
                next_actions=self._cart_next_actions(updated),
            )

        if action.name == "remove_item":
            cart = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            item_id = params.get("itemId")
            if not item_id and params.get("productId"):
                match = next(
                    (item for item in cart["items"] if item["productId"] == params.get("productId")),
                    None,
                )
                if match:
                    item_id = match["itemId"]
            if not item_id and cart["items"]:
                item_id = cart["items"][0]["itemId"]
            if not item_id:
                return AgentExecutionResult(
                    success=False,
                    message="Your cart is empty.",
                    data={"cart": cart},
                )

            self.cart_service.remove_item(user_id=user_id, session_id=session_id, item_id=str(item_id))
            updated = self.cart_service.get_cart(user_id=user_id, session_id=session_id)
            return AgentExecutionResult(
                success=True,
                message=f"Removed item. Cart total is ${updated['total']:.2f}.",
                data={"cart": updated},
                next_actions=self._cart_next_actions(updated),
            )

        raise HTTPException(status_code=400, detail=f"Unsupported cart action: {action.name}")

    def _infer_from_recent(self, recent: list[dict[str, Any]]) -> dict[str, Any]:
        for record in reversed(recent):
            data = record.get("response", {}).get("data", {})
            products = data.get("products", [])
            if products:
                first = products[0]
                variants = first.get("variants", [])
                if variants:
                    return {"productId": first.get("id"), "variantId": variants[0].get("id")}
        return {}

    def _cart_next_actions(self, cart: dict[str, Any]) -> list[dict[str, str]]:
        actions = [{"label": "Continue shopping", "action": "search:more"}]
        if cart["itemCount"] > 0:
            actions.append({"label": "Checkout", "action": "checkout"})
        return actions

