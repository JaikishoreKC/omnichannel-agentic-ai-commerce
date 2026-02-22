from __future__ import annotations

from typing import Any

from app.store.in_memory import InMemoryStore


class NotificationService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def send_order_confirmation(self, *, user_id: str, order: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": f"notif_{self.store.next_id('item')}",
            "type": "order_confirmation",
            "userId": user_id,
            "orderId": order["id"],
            "message": f"Order {order['id']} confirmed for ${order['total']:.2f}",
            "createdAt": self.store.iso_now(),
        }
        with self.store.lock:
            self.store.notifications.append(payload)
        return payload

