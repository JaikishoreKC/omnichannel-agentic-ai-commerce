from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.store.in_memory import InMemoryStore


class InventoryService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def get_variant_inventory(self, variant_id: str) -> dict[str, Any]:
        with self.store.lock:
            stock = self.store.inventory_by_variant.get(variant_id)
            if not stock:
                raise HTTPException(status_code=404, detail="Inventory variant not found")
            return dict(stock)

    def update_variant_inventory(
        self,
        *,
        variant_id: str,
        total_quantity: int | None = None,
        available_quantity: int | None = None,
    ) -> dict[str, Any]:
        with self.store.lock:
            stock = self.store.inventory_by_variant.get(variant_id)
            if not stock:
                raise HTTPException(status_code=404, detail="Inventory variant not found")

            if total_quantity is not None:
                stock["totalQuantity"] = max(0, int(total_quantity))
            if available_quantity is not None:
                stock["availableQuantity"] = max(0, int(available_quantity))

            # Keep reservations coherent with totals.
            max_reserved = max(0, stock["totalQuantity"] - stock["availableQuantity"])
            stock["reservedQuantity"] = min(stock["reservedQuantity"], max_reserved)
            stock["updatedAt"] = self.store.iso_now()
            self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])
            return dict(stock)

    def reserve_for_order(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reserve inventory for order creation.

        Returns reservation snapshots used to rollback on payment failure.
        """
        reservations: list[dict[str, Any]] = []
        with self.store.lock:
            # Validate all items first.
            for item in items:
                variant_id = item["variantId"]
                quantity = int(item["quantity"])
                stock = self.store.inventory_by_variant.get(variant_id)
                if not stock:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Inventory not found for variant {variant_id}",
                    )
                if stock["availableQuantity"] < quantity:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Insufficient inventory for variant {variant_id}",
                    )

            # Reserve quantities.
            for item in items:
                variant_id = item["variantId"]
                quantity = int(item["quantity"])
                stock = self.store.inventory_by_variant[variant_id]
                snapshot = {
                    "variantId": variant_id,
                    "reservedQuantity": stock["reservedQuantity"],
                    "availableQuantity": stock["availableQuantity"],
                }
                reservations.append(snapshot)
                stock["reservedQuantity"] += quantity
                stock["availableQuantity"] -= quantity
                stock["updatedAt"] = self.store.iso_now()
                self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])

        return reservations

    def commit_reservation(self, items: list[dict[str, Any]]) -> None:
        with self.store.lock:
            for item in items:
                variant_id = item["variantId"]
                quantity = int(item["quantity"])
                stock = self.store.inventory_by_variant.get(variant_id)
                if not stock:
                    continue
                stock["reservedQuantity"] = max(0, stock["reservedQuantity"] - quantity)
                stock["totalQuantity"] = max(0, stock["totalQuantity"] - quantity)
                stock["updatedAt"] = self.store.iso_now()
                self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])

    def rollback_reservation(self, snapshots: list[dict[str, Any]]) -> None:
        with self.store.lock:
            for snapshot in snapshots:
                variant_id = snapshot["variantId"]
                stock = self.store.inventory_by_variant.get(variant_id)
                if not stock:
                    continue
                stock["reservedQuantity"] = snapshot["reservedQuantity"]
                stock["availableQuantity"] = snapshot["availableQuantity"]
                stock["updatedAt"] = self.store.iso_now()
                self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])

    def _sync_variant_stock_flag(self, *, variant_id: str, available: int) -> None:
        for product in self.store.products_by_id.values():
            for variant in product["variants"]:
                if variant["id"] == variant_id:
                    variant["inStock"] = available > 0
                    return
