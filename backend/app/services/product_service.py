from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import HTTPException

from app.store.in_memory import InMemoryStore


class ProductService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def list_products(
        self,
        query: str | None,
        category: str | None,
        min_price: float | None,
        max_price: float | None,
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        normalized_query = (query or "").strip().lower()
        normalized_category = (category or "").strip().lower()
        safe_page = max(1, page)
        safe_limit = min(100, max(1, limit))

        with self.store.lock:
            products = [deepcopy(item) for item in self.store.products_by_id.values()]

        def matches(item: dict[str, Any]) -> bool:
            if normalized_query:
                haystack = f"{item['name']} {item['description']}".lower()
                if normalized_query not in haystack:
                    return False
            if normalized_category and item["category"].lower() != normalized_category:
                return False
            if min_price is not None and item["price"] < min_price:
                return False
            if max_price is not None and item["price"] > max_price:
                return False
            return True

        filtered = [item for item in products if matches(item)]
        total = len(filtered)
        start = (safe_page - 1) * safe_limit
        end = start + safe_limit
        page_items = filtered[start:end]

        return {
            "products": page_items,
            "pagination": {
                "page": safe_page,
                "limit": safe_limit,
                "total": total,
                "pages": (total + safe_limit - 1) // safe_limit if total else 0,
            },
        }

    def get_product(self, product_id: str) -> dict[str, Any]:
        with self.store.lock:
            product = self.store.products_by_id.get(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            return deepcopy(product)

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            product_id = payload.get("id") or self.store.next_id("item").replace("item", "prod")
            if product_id in self.store.products_by_id:
                raise HTTPException(status_code=409, detail="Product ID already exists")

            product = {
                "id": product_id,
                "name": payload["name"],
                "description": payload.get("description", ""),
                "category": payload["category"],
                "price": float(payload["price"]),
                "currency": payload.get("currency", "USD"),
                "images": list(payload.get("images", [])),
                "variants": deepcopy(payload.get("variants", [])),
                "rating": float(payload.get("rating", 0.0)),
                "reviewCount": int(payload.get("reviewCount", 0)),
            }
            self.store.products_by_id[product_id] = product
            self._sync_variant_inventory(product_id=product_id, variants=product["variants"], replace_existing=False)

            return deepcopy(product)

    def update_product(self, product_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            product = self.store.products_by_id.get(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            for key in ("name", "description", "category", "price", "currency", "images", "rating", "reviewCount"):
                if key in patch and patch[key] is not None:
                    value = patch[key]
                    if key == "price":
                        value = float(value)
                    elif key == "reviewCount":
                        value = int(value)
                    elif key == "rating":
                        value = float(value)
                    elif key == "images":
                        value = list(value)
                    product[key] = value
            if "variants" in patch and patch["variants"] is not None:
                product["variants"] = deepcopy(patch["variants"])
                self._sync_variant_inventory(
                    product_id=product_id,
                    variants=product["variants"],
                    replace_existing=True,
                )
            return deepcopy(product)

    def delete_product(self, product_id: str) -> None:
        with self.store.lock:
            product = self.store.products_by_id.pop(product_id, None)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            for variant in product.get("variants", []):
                self.store.inventory_by_variant.pop(variant["id"], None)

    def list_categories(self) -> dict[str, Any]:
        with self.store.lock:
            categories = sorted({product["category"] for product in self.store.products_by_id.values()})
            return {"categories": categories}

    def _sync_variant_inventory(
        self,
        *,
        product_id: str,
        variants: list[dict[str, Any]],
        replace_existing: bool,
    ) -> None:
        incoming_ids = {variant["id"] for variant in variants}
        if replace_existing:
            to_delete = [
                variant_id
                for variant_id, stock in self.store.inventory_by_variant.items()
                if stock["productId"] == product_id and variant_id not in incoming_ids
            ]
            for variant_id in to_delete:
                self.store.inventory_by_variant.pop(variant_id, None)

        for variant in variants:
            variant_id = variant["id"]
            inventory = variant.get("inventory") or {}
            existing = self.store.inventory_by_variant.get(variant_id)
            if existing:
                total_quantity = int(inventory.get("totalQuantity", existing["totalQuantity"]))
                available_quantity = int(
                    inventory.get("availableQuantity", existing["availableQuantity"])
                )
                reserved_quantity = int(existing.get("reservedQuantity", 0))
            else:
                available_quantity = int(inventory.get("availableQuantity", 10))
                total_quantity = int(inventory.get("totalQuantity", available_quantity))
                reserved_quantity = 0
            total_quantity = max(0, total_quantity)
            reserved_quantity = max(0, min(reserved_quantity, total_quantity))
            available_quantity = max(0, min(available_quantity, total_quantity - reserved_quantity))

            self.store.inventory_by_variant[variant_id] = {
                "variantId": variant_id,
                "productId": product_id,
                "totalQuantity": total_quantity,
                "reservedQuantity": reserved_quantity,
                "availableQuantity": available_quantity,
                "updatedAt": self.store.iso_now(),
            }
            variant["inStock"] = available_quantity > 0
