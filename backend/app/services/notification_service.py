from __future__ import annotations

from typing import Any

from app.repositories.notification_repository import NotificationRepository
from app.core.utils import generate_id, iso_now


class NotificationService:
    def __init__(
        self,
        notification_repository: NotificationRepository,
    ) -> None:
        self.notification_repository = notification_repository

    def send_order_confirmation(self, *, user_id: str, order: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": generate_id("notif"),
            "type": "order_confirmation",
            "userId": user_id,
            "orderId": order["id"],
            "message": f"Order {order['id']} confirmed for ${order['total']:.2f}",
            "createdAt": iso_now(),
        }
        self.notification_repository.create(payload)
        return payload

    def send_voice_recovery_followup(
        self,
        *,
        user_id: str,
        call_id: str,
        message: str,
        disposition: str,
    ) -> dict[str, Any]:
        payload = {
            "id": generate_id("notif"),
            "type": "voice_recovery_followup",
            "userId": user_id,
            "callId": call_id,
            "disposition": disposition,
            "message": message,
            "createdAt": iso_now(),
        }
        self.notification_repository.create(payload)
        return payload
