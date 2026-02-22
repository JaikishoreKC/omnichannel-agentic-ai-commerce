from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.order_service import OrderService


class OrderAgent(BaseAgent):
    name = "order"

    def __init__(self, order_service: OrderService) -> None:
        self.order_service = order_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = context.user_id

        if action.name == "checkout_summary":
            if not user_id:
                return AgentExecutionResult(
                    success=False,
                    message="Login required before order creation. Your cart is preserved.",
                    data={"code": "AUTH_REQUIRED"},
                    next_actions=[
                        {"label": "Login", "action": "auth:login"},
                        {"label": "View cart", "action": "view_cart"},
                    ],
                )
            if not context.cart or context.cart["itemCount"] == 0:
                return AgentExecutionResult(
                    success=False,
                    message="Your cart is empty. Add products before checkout.",
                    data={},
                )

            idempotency_key = f"{context.session_id}:{len(context.recent_messages)}"
            order = self.order_service.create_order(
                user_id=user_id,
                shipping_address={
                    "name": "Default Customer",
                    "line1": "123 Main St",
                    "city": "Austin",
                    "state": "TX",
                    "postalCode": "78701",
                    "country": "US",
                },
                payment_method={"type": "card", "token": "pm_chat_default"},
                idempotency_key=idempotency_key,
            )
            return AgentExecutionResult(
                success=True,
                message=f"Checkout complete. Order {order['id']} confirmed.",
                data={"order": order},
                next_actions=[
                    {"label": "Track order", "action": f"order_status:{order['id']}"},
                    {"label": "Continue shopping", "action": "search:more"},
                ],
            )

        if action.name == "get_order_status":
            if not user_id:
                return AgentExecutionResult(
                    success=False,
                    message="Please log in to view order status.",
                    data={"code": "AUTH_REQUIRED"},
                )

            order_id = action.params.get("orderId")
            if order_id:
                order = self.order_service.get_order(user_id=user_id, order_id=str(order_id))
                return AgentExecutionResult(
                    success=True,
                    message=f"Order {order['id']} is currently {order['status']}.",
                    data={"order": order},
                )

            orders = self.order_service.list_orders(user_id=user_id)["orders"]
            if not orders:
                return AgentExecutionResult(
                    success=True,
                    message="No orders found yet.",
                    data={"orders": []},
                )
            latest = orders[0]
            return AgentExecutionResult(
                success=True,
                message=f"Latest order {latest['id']} is {latest['status']}.",
                data={"orders": orders[:5]},
                next_actions=[{"label": "Track latest order", "action": f"order_status:{latest['id']}"}],
            )

        if action.name == "cancel_order":
            if not user_id:
                return AgentExecutionResult(
                    success=False,
                    message="Please log in to cancel orders.",
                    data={"code": "AUTH_REQUIRED"},
                )
            order_id = action.params.get("orderId")
            if not order_id:
                orders = self.order_service.list_orders(user_id=user_id)["orders"]
                if not orders:
                    return AgentExecutionResult(
                        success=False,
                        message="You have no order to cancel.",
                        data={},
                    )
                order_id = orders[0]["id"]
            result = self.order_service.cancel_order(
                user_id=user_id,
                order_id=str(order_id),
                reason=action.params.get("reason"),
            )
            return AgentExecutionResult(
                success=True,
                message=f"Order {result['orderId']} has been cancelled.",
                data=result,
                next_actions=[{"label": "Continue shopping", "action": "search:more"}],
            )

        if action.name == "request_refund":
            if not user_id:
                return AgentExecutionResult(
                    success=False,
                    message="Please log in to request refunds.",
                    data={"code": "AUTH_REQUIRED"},
                )
            order_id = action.params.get("orderId")
            if not order_id:
                orders = self.order_service.list_orders(user_id=user_id)["orders"]
                if not orders:
                    return AgentExecutionResult(
                        success=False,
                        message="You have no order available for refund.",
                        data={},
                    )
                order_id = orders[0]["id"]
            result = self.order_service.request_refund(
                user_id=user_id,
                order_id=str(order_id),
                reason=action.params.get("reason"),
            )
            return AgentExecutionResult(
                success=True,
                message=f"Refund request completed for order {result['orderId']}.",
                data=result,
                next_actions=[{"label": "Track order", "action": f"order_status:{result['orderId']}"}],
            )

        if action.name == "change_order_address":
            if not user_id:
                return AgentExecutionResult(
                    success=False,
                    message="Please log in to change order addresses.",
                    data={"code": "AUTH_REQUIRED"},
                )
            order_id = action.params.get("orderId")
            if not order_id:
                orders = self.order_service.list_orders(user_id=user_id)["orders"]
                if not orders:
                    return AgentExecutionResult(
                        success=False,
                        message="You have no order available for address updates.",
                        data={},
                    )
                order_id = orders[0]["id"]

            shipping_address = action.params.get("shippingAddress")
            if not isinstance(shipping_address, dict):
                return AgentExecutionResult(
                    success=False,
                    message=(
                        "I can update shipping on eligible orders. Provide fields like "
                        "line1=500 Main St, city=Austin, state=TX, postalCode=78701, country=US."
                    ),
                    data={"orderId": str(order_id)},
                )

            result = self.order_service.update_shipping_address(
                user_id=user_id,
                order_id=str(order_id),
                shipping_address=shipping_address,
            )
            return AgentExecutionResult(
                success=True,
                message=f"Updated shipping address for order {result['orderId']}.",
                data=result,
                next_actions=[{"label": "Track order", "action": f"order_status:{result['orderId']}"}],
            )

        raise HTTPException(status_code=400, detail=f"Unsupported order action: {action.name}")
