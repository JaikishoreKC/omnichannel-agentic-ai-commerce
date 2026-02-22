from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from fastapi import HTTPException

from app.services.cart_service import CartService
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from app.store.in_memory import InMemoryStore


class OrderService:
    def __init__(
        self,
        store: InMemoryStore,
        cart_service: CartService,
        inventory_service: InventoryService,
        payment_service: PaymentService,
        notification_service: NotificationService,
    ) -> None:
        self.store = store
        self.cart_service = cart_service
        self.inventory_service = inventory_service
        self.payment_service = payment_service
        self.notification_service = notification_service

    def create_order(
        self,
        user_id: str,
        shipping_address: dict[str, Any],
        payment_method: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not idempotency_key.strip():
            raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")

        key = f"{user_id}:{idempotency_key.strip()}"
        with self.store.lock:
            existing_order_id = self.store.idempotency_keys.get(key)
            if existing_order_id:
                return deepcopy(self.store.orders_by_id[existing_order_id])

        cart = self.cart_service.get_cart(user_id=user_id, session_id="")
        if not cart["items"]:
            raise HTTPException(status_code=400, detail="Cart is empty")

        reservations = self.inventory_service.reserve_for_order(cart["items"])
        payment_result: dict[str, Any] | None = None
        try:
            payment_result = self.payment_service.authorize(
                amount=float(cart["total"]),
                payment_method=payment_method,
            )
        except Exception:
            self.inventory_service.rollback_reservation(reservations)
            raise

        with self.store.lock:
            order_id = self.store.next_id("order")
            created_at = self.store.iso_now()
            estimated_delivery = (self.store.utc_now() + timedelta(days=5)).isoformat()
            order = {
                "id": order_id,
                "userId": user_id,
                "status": "confirmed",
                "items": deepcopy(cart["items"]),
                "subtotal": cart["subtotal"],
                "tax": cart["tax"],
                "shipping": cart["shipping"],
                "discount": cart["discount"],
                "total": cart["total"],
                "shippingAddress": shipping_address,
                "payment": {
                    "method": payment_result.get("method") if payment_result else "unknown",
                    "transactionId": payment_result.get("transactionId") if payment_result else None,
                    "status": payment_result.get("status") if payment_result else "failed",
                },
                "timeline": [
                    {"status": "order_placed", "timestamp": created_at},
                    {"status": "confirmed", "timestamp": created_at},
                ],
                "tracking": {
                    "carrier": None,
                    "trackingNumber": None,
                    "status": "pending",
                    "updates": [],
                },
                "estimatedDelivery": estimated_delivery,
                "createdAt": created_at,
                "updatedAt": created_at,
            }
            self.store.orders_by_id[order_id] = order
            self.store.idempotency_keys[key] = order_id

            # Clear cart after successful conversion.
            for candidate in self.store.carts_by_id.values():
                if candidate.get("userId") == user_id:
                    candidate["items"] = []
                    candidate["appliedDiscount"] = None
                    self.cart_service._recalculate_cart(candidate)  # noqa: SLF001
                    break

            self.inventory_service.commit_reservation(order["items"])
            self.notification_service.send_order_confirmation(user_id=user_id, order=order)

            return deepcopy(order)

    def list_orders(self, user_id: str) -> dict[str, Any]:
        with self.store.lock:
            orders = [order for order in self.store.orders_by_id.values() if order["userId"] == user_id]
            orders.sort(key=lambda order: order["createdAt"], reverse=True)
            return {
                "orders": [
                    {
                        "id": order["id"],
                        "status": order["status"],
                        "total": order["total"],
                        "itemCount": sum(int(item.get("quantity", 0)) for item in order["items"]),
                        "createdAt": order["createdAt"],
                    }
                    for order in orders
                ]
            }

    def get_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        with self.store.lock:
            order = self.store.orders_by_id.get(order_id)
            if not order or order["userId"] != user_id:
                raise HTTPException(status_code=404, detail="Order not found")
            return deepcopy(order)

    def cancel_order(self, user_id: str, order_id: str, reason: str | None) -> dict[str, Any]:
        with self.store.lock:
            order = self.store.orders_by_id.get(order_id)
            if not order or order["userId"] != user_id:
                raise HTTPException(status_code=404, detail="Order not found")
            if order["status"] in {"shipped", "delivered", "cancelled", "refunded"}:
                raise HTTPException(status_code=409, detail="Order can no longer be cancelled")

            order["status"] = "cancelled"
            order["updatedAt"] = self.store.iso_now()
            order["timeline"].append(
                {
                    "status": "cancelled",
                    "timestamp": order["updatedAt"],
                    "note": reason or "Cancelled by customer",
                }
            )
            return {"success": True, "orderId": order_id, "status": "cancelled"}
