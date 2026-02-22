from __future__ import annotations

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
            products = list(self.store.products_by_id.values())

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
            return product

