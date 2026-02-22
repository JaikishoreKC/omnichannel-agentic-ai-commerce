from __future__ import annotations

import re
from typing import Any

from app.orchestrator.types import IntentResult


class IntentClassifier:
    """Lightweight rule-first classifier for commerce intents."""

    def classify(self, message: str, context: dict[str, Any] | None = None) -> IntentResult:
        text = message.strip().lower()
        entities: dict[str, Any] = {}

        if not text:
            return IntentResult(name="general_question", confidence=0.2, entities={})

        if ("cart" in text or "my cart" in text) and (
            "order status" in text or "where is my order" in text or "track order" in text
        ):
            entities.update(self._extract_order_id(text))
            return IntentResult(name="multi_status", confidence=0.9, entities=entities)

        # Order intents.
        if "cancel" in text and "order" in text:
            entities.update(self._extract_order_id(text))
            return IntentResult(name="cancel_order", confidence=0.91, entities=entities)
        if "order status" in text or "where is my order" in text or "track order" in text:
            entities.update(self._extract_order_id(text))
            return IntentResult(name="order_status", confidence=0.9, entities=entities)
        if "checkout" in text or "place order" in text or "buy now" in text:
            return IntentResult(name="checkout", confidence=0.95, entities={})

        # Cart intents.
        if "remove" in text and "cart" in text:
            entities.update(self._extract_product_or_item_id(text))
            return IntentResult(name="remove_from_cart", confidence=0.88, entities=entities)
        if any(phrase in text for phrase in ["update cart", "change quantity", "set quantity"]):
            entities.update(self._extract_quantity(text))
            entities.update(self._extract_product_or_item_id(text))
            return IntentResult(name="update_cart", confidence=0.86, entities=entities)
        if "add" in text and "cart" in text:
            entities.update(self._extract_quantity(text))
            entities.update(self._extract_product_or_variant_id(text))
            return IntentResult(name="add_to_cart", confidence=0.92, entities=entities)
        if "show cart" in text or "my cart" in text:
            return IntentResult(name="view_cart", confidence=0.9, entities={})

        # Product intents.
        if any(token in text for token in ["find", "search", "show me", "recommend", "looking for"]):
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_color(text))
            entities["query"] = message.strip()
            return IntentResult(name="product_search", confidence=0.84, entities=entities)

        return IntentResult(name="general_question", confidence=0.6, entities={"query": message.strip()})

    def _extract_order_id(self, text: str) -> dict[str, Any]:
        match = re.search(r"(order[_\-]?\d+|ord[_\-]?\d+)", text)
        return {"orderId": match.group(1)} if match else {}

    def _extract_quantity(self, text: str) -> dict[str, Any]:
        match = re.search(r"\b(\d+)\b", text)
        if not match:
            return {}
        quantity = max(1, min(50, int(match.group(1))))
        return {"quantity": quantity}

    def _extract_color(self, text: str) -> dict[str, Any]:
        for color in ("black", "blue", "white", "green", "red", "gray", "charcoal", "navy"):
            if color in text:
                return {"color": color}
        return {}

    def _extract_price_range(self, text: str) -> dict[str, Any]:
        below = re.search(r"(under|below)\s*\$?(\d+)", text)
        above = re.search(r"(over|above)\s*\$?(\d+)", text)
        entities: dict[str, Any] = {}
        if below:
            entities["maxPrice"] = float(below.group(2))
        if above:
            entities["minPrice"] = float(above.group(2))
        return entities

    def _extract_product_or_variant_id(self, text: str) -> dict[str, Any]:
        product_match = re.search(r"(prod[_\-]?\d+)", text)
        variant_match = re.search(r"(var[_\-]?\d+)", text)
        entities: dict[str, Any] = {}
        if product_match:
            entities["productId"] = product_match.group(1).replace("-", "_")
        if variant_match:
            entities["variantId"] = variant_match.group(1).replace("-", "_")
        return entities

    def _extract_product_or_item_id(self, text: str) -> dict[str, Any]:
        item_match = re.search(r"(item[_\-]?\d+)", text)
        if item_match:
            return {"itemId": item_match.group(1).replace("-", "_")}
        return self._extract_product_or_variant_id(text)
