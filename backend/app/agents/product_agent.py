from __future__ import annotations

import re
from typing import Any

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.product_service import ProductService


class ProductAgent(BaseAgent):
    name = "product"

    def __init__(self, product_service: ProductService) -> None:
        self.product_service = product_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        params = action.params
        raw_query = str(params.get("query", "")).strip()
        query = self._normalize_query(raw_query)
        if self._should_browse_without_query(raw_query=raw_query, normalized_query=query):
            query = ""
        category = self._infer_category(query) or self._preferred_category(context)
        results = self.product_service.list_products(
            query=query or None,
            category=category,
            min_price=params.get("minPrice"),
            max_price=params.get("maxPrice"),
            page=1,
            limit=8,
        )

        if "color" in params:
            color = str(params["color"]).lower()
            filtered_products: list[dict[str, Any]] = []
            for product in results["products"]:
                if any(v["color"].lower() == color for v in product["variants"]):
                    filtered_products.append(product)
            results["products"] = filtered_products
            results["pagination"]["total"] = len(filtered_products)
            results["pagination"]["pages"] = 1

        products = self._sort_with_affinity(results["products"], context=context)
        results["products"] = products
        if not products:
            return AgentExecutionResult(
                success=True,
                message="I couldn't find matching products. Want to broaden filters?",
                data={"products": [], "pagination": results["pagination"]},
                next_actions=[
                    {"label": "Show all products", "action": "search:all"},
                    {"label": "Set max price $150", "action": "search:under_150"},
                ],
            )

        top = products[0]
        top_variant = top["variants"][0]["id"] if top.get("variants") else ""
        next_actions = [{"label": "Show my cart", "action": "view_cart"}]
        if top_variant:
            next_actions.insert(
                0,
                {
                    "label": f"Add {top['name']}",
                    "action": f"add_to_cart:{top['id']}:{top_variant}",
                },
            )
        return AgentExecutionResult(
            success=True,
            message=f"I found {len(products)} options. Top result: {top['name']} (${top['price']:.2f}).",
            data={"products": products, "pagination": results["pagination"]},
            next_actions=next_actions,
        )

    def _infer_category(self, query: str) -> str | None:
        lower = query.lower()
        if "shoe" in lower or "runner" in lower:
            return "shoes"
        if "hoodie" in lower or "jogger" in lower:
            return "clothing"
        if "sock" in lower or "backpack" in lower:
            return "accessories"
        return None

    def _normalize_query(self, query: str) -> str:
        lowered = query.lower()
        lowered = re.sub(
            r"\b(show me|find|search|looking for|i need|i want|please|recommend|suggest)\b",
            " ",
            lowered,
        )
        lowered = re.sub(r"\b(under|below|over|above)\s*\$?\d+\b", " ", lowered)
        lowered = re.sub(r"\b(something|anything|options)\b", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _should_browse_without_query(self, *, raw_query: str, normalized_query: str) -> bool:
        lower = raw_query.lower()
        if any(token in lower for token in ("recommend", "suggest", "anything", "something")):
            return True
        return normalized_query in {"", "me", "for me"}

    def _preferred_category(self, context: AgentContext) -> str | None:
        preferences = context.preferences or {}
        preferred_categories = preferences.get("categories") if isinstance(preferences, dict) else None
        if isinstance(preferred_categories, list) and preferred_categories:
            return str(preferred_categories[0]).strip().lower() or None

        memory = context.memory or {}
        affinities = memory.get("productAffinities") if isinstance(memory, dict) else None
        category_scores = affinities.get("categories", {}) if isinstance(affinities, dict) else {}
        if isinstance(category_scores, dict) and category_scores:
            return str(max(category_scores.items(), key=lambda item: int(item[1]))[0]).lower()
        return None

    def _sort_with_affinity(
        self, products: list[dict[str, Any]], *, context: AgentContext
    ) -> list[dict[str, Any]]:
        memory = context.memory or {}
        affinities = memory.get("productAffinities") if isinstance(memory, dict) else None
        if not isinstance(affinities, dict):
            return products

        product_scores = affinities.get("products", {})
        category_scores = affinities.get("categories", {})
        if not isinstance(product_scores, dict) or not isinstance(category_scores, dict):
            return products

        def rank(item: dict[str, Any]) -> tuple[int, int, float]:
            product_id = str(item.get("id", ""))
            category = str(item.get("category", "")).strip().lower()
            direct = int(product_scores.get(product_id, 0))
            by_category = int(category_scores.get(category, 0))
            rating = float(item.get("rating", 0.0))
            return (direct, by_category, rating)

        return sorted(products, key=rank, reverse=True)
