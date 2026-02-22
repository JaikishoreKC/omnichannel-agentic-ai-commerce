from __future__ import annotations

import re
from typing import Any

from app.infrastructure.llm_client import LLMClient
from app.orchestrator.types import IntentResult


class IntentClassifier:
    """Lightweight rule-first classifier for commerce intents."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def classify(self, message: str, context: dict[str, Any] | None = None) -> IntentResult:
        rule_intent = self._classify_rules(message=message, context=context)
        llm_choice = self._classify_with_llm(message=message, context=context)
        if llm_choice is None:
            return rule_intent
        if llm_choice.confidence >= max(0.7, rule_intent.confidence):
            return llm_choice
        return rule_intent

    def _classify_with_llm(self, *, message: str, context: dict[str, Any] | None) -> IntentResult | None:
        if self.llm_client is None:
            return None
        recent = []
        if context:
            raw_recent = context.get("recent", [])
            if isinstance(raw_recent, list):
                recent = [item for item in raw_recent if isinstance(item, dict)]
        prediction = self.llm_client.classify_intent(message=message, recent_messages=recent)
        if prediction is None:
            return None
        return IntentResult(
            name=prediction.intent,
            confidence=prediction.confidence,
            entities=prediction.entities,
        )

    def _classify_rules(self, *, message: str, context: dict[str, Any] | None = None) -> IntentResult:
        text = message.strip().lower()
        entities: dict[str, Any] = {}

        if not text:
            return IntentResult(name="general_question", confidence=0.2, entities={})

        if ("cart" in text or "my cart" in text) and self._contains_order_status_phrase(text):
            entities.update(self._extract_order_id(text))
            return IntentResult(name="multi_status", confidence=0.9, entities=entities)

        # Order intents.
        if "order" in text and "address" in text and any(token in text for token in ("change", "update", "delivery")):
            entities.update(self._extract_order_id(text))
            entities.update(self._extract_shipping_address(message))
            return IntentResult(name="change_order_address", confidence=0.88, entities=entities)
        if "cancel" in text and "order" in text:
            entities.update(self._extract_order_id(text))
            return IntentResult(name="cancel_order", confidence=0.91, entities=entities)
        if "refund" in text and "order" in text:
            entities.update(self._extract_order_id(text))
            return IntentResult(name="request_refund", confidence=0.9, entities=entities)
        if self._contains_order_status_phrase(text):
            entities.update(self._extract_order_id(text))
            return IntentResult(name="order_status", confidence=0.9, entities=entities)
        if "checkout" in text or "place order" in text or "buy now" in text:
            return IntentResult(name="checkout", confidence=0.95, entities={})

        if ("add" in text and "cart" in text) and any(
            token in text
            for token in (
                "find",
                "search",
                "show me",
                "recommend",
                "looking for",
                "under",
                "below",
                "over",
                "above",
            )
        ):
            entities.update(self._extract_quantity(text))
            entities.update(self._extract_product_or_variant_id(text))
            entities.update(self._extract_price_range(text))
            entities.update(self._extract_color(text))
            entities["query"] = self._extract_search_query_for_combo(message)
            return IntentResult(name="search_and_add_to_cart", confidence=0.93, entities=entities)

        # Cart intents.
        if any(token in text for token in ("discount", "coupon", "promo")) and any(
            token in text for token in ("apply", "use", "code")
        ):
            entities.update(self._extract_discount_code(message))
            return IntentResult(name="apply_discount", confidence=0.9, entities=entities)
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

    def _contains_order_status_phrase(self, text: str) -> bool:
        if "order" not in text:
            return False
        phrases = (
            "order status",
            "where is my order",
            "track order",
            "hasn't arrived",
            "hasnt arrived",
            "not arrived",
            "order is late",
            "order late",
            "delayed order",
            "order delayed",
        )
        return any(phrase in text for phrase in phrases)

    def _extract_discount_code(self, message: str) -> dict[str, Any]:
        explicit = re.search(
            r"(?:code|coupon|promo)\s*(?:is|=|:)?\s*([a-zA-Z0-9_-]{4,20})",
            message,
            flags=re.IGNORECASE,
        )
        if explicit:
            return {"code": explicit.group(1).upper()}

        candidates = re.findall(r"\b([A-Za-z0-9]{4,20})\b", message)
        stop_words = {"APPLY", "DISCOUNT", "COUPON", "PROMO", "CODE", "PLEASE", "THIS", "THAT"}
        for candidate in candidates:
            token = candidate.upper()
            if token not in stop_words and any(char.isdigit() for char in token):
                return {"code": token}
        return {}

    def _extract_search_query_for_combo(self, message: str) -> str:
        cleaned = re.sub(
            r"\b(and\s+)?(add|put)\b.*\bcart\b",
            " ",
            message,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _extract_shipping_address(self, message: str) -> dict[str, Any]:
        patterns = {
            "name": r"name",
            "line1": r"line1|address|street",
            "line2": r"line2|apt|suite",
            "city": r"city",
            "state": r"state",
            "postalCode": r"postal\s*code|postalcode|zip",
            "country": r"country",
        }
        fields: dict[str, str] = {}
        for field, pattern in patterns.items():
            match = re.search(
                rf"(?:{pattern})\s*[:=]\s*([^,;]+)",
                message,
                flags=re.IGNORECASE,
            )
            if match:
                fields[field] = match.group(1).strip()

        required = {"line1", "city", "state", "postalCode", "country"}
        if not required.issubset(fields.keys()):
            return {}
        shipping = {
            "name": fields.get("name", "Customer"),
            "line1": fields["line1"],
            "city": fields["city"],
            "state": fields["state"],
            "postalCode": fields["postalCode"],
            "country": fields["country"],
        }
        if "line2" in fields:
            shipping["line2"] = fields["line2"]
        return {"shippingAddress": shipping}
