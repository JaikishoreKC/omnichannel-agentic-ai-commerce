from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.store.in_memory import InMemoryStore


class PaymentService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def authorize(self, *, amount: float, payment_method: dict[str, Any]) -> dict[str, Any]:
        payment_type = str(payment_method.get("type", ""))
        token = str(payment_method.get("token", ""))
        if payment_type != "card" or not token:
            raise HTTPException(status_code=400, detail="Invalid payment method")
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid payment amount")

        transaction_id = f"txn_{self.store.next_id('payment')}"
        return {
            "status": "authorized",
            "transactionId": transaction_id,
            "method": payment_type,
        }
