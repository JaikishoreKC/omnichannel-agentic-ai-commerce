from __future__ import annotations

from app.store.in_memory import InMemoryStore


class AdminService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def stats(self) -> dict[str, object]:
        with self.store.lock:
            active_sessions = len(self.store.sessions_by_id)
            orders = list(self.store.orders_by_id.values())
            orders_today = len(orders)
            revenue_today = round(sum(order["total"] for order in orders), 2)

            by_product: dict[str, dict[str, object]] = {}
            for order in orders:
                for item in order["items"]:
                    product_id = item["productId"]
                    product = self.store.products_by_id.get(product_id, {"name": "Unknown"})
                    row = by_product.setdefault(
                        product_id,
                        {"id": product_id, "name": product["name"], "sold": 0},
                    )
                    row["sold"] = int(row["sold"]) + int(item["quantity"])

            top_products = sorted(
                by_product.values(), key=lambda item: int(item["sold"]), reverse=True
            )[:5]
            return {
                "activeSessions": active_sessions,
                "ordersToday": orders_today,
                "revenueToday": revenue_today,
                "topProducts": top_products,
            }

