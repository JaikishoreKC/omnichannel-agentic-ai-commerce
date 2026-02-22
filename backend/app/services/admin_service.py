from __future__ import annotations

from app.store.in_memory import InMemoryStore


class AdminService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def stats(self) -> dict[str, object]:
        with self.store.lock:
            today = self.store.utc_now().date().isoformat()
            active_sessions = len(self.store.sessions_by_id)
            orders = list(self.store.orders_by_id.values())
            orders_today_rows = [order for order in orders if str(order.get("createdAt", ""))[:10] == today]
            orders_today = len(orders_today_rows)
            revenue_today = round(sum(float(order["total"]) for order in orders_today_rows), 2)

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

            interactions = [
                record
                for rows in self.store.messages_by_session.values()
                for record in rows
                if str(record.get("timestamp", ""))[:10] == today
            ]
            by_agent: dict[str, dict[str, object]] = {}
            for record in interactions:
                agent = str(record.get("agent", "unknown"))
                row = by_agent.setdefault(
                    agent,
                    {"agent": agent, "interactions": 0, "successfulInteractions": 0},
                )
                row["interactions"] = int(row["interactions"]) + 1
                metadata = (record.get("response") or {}).get("metadata", {})
                if bool(metadata.get("success")):
                    row["successfulInteractions"] = int(row["successfulInteractions"]) + 1

            agent_performance = []
            for row in by_agent.values():
                interactions_count = int(row["interactions"])
                success_count = int(row["successfulInteractions"])
                success_rate = round(
                    (success_count / interactions_count) * 100 if interactions_count else 0.0,
                    2,
                )
                agent_performance.append(
                    {
                        "agent": row["agent"],
                        "interactions": interactions_count,
                        "successRate": success_rate,
                    }
                )
            agent_performance.sort(key=lambda item: int(item["interactions"]), reverse=True)

            open_tickets = [ticket for ticket in self.store.support_tickets if ticket.get("status") == "open"]
            return {
                "activeSessions": active_sessions,
                "ordersToday": orders_today,
                "revenueToday": revenue_today,
                "topProducts": top_products,
                "messagesToday": len(interactions),
                "supportOpenTickets": len(open_tickets),
                "agentPerformance": agent_performance,
            }
