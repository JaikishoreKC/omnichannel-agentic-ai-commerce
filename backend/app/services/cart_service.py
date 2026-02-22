from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import HTTPException

from app.core.config import Settings
from app.store.in_memory import InMemoryStore


class CartService:
    def __init__(self, store: InMemoryStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    def get_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        return deepcopy(cart)

    def add_item(
        self,
        user_id: str | None,
        session_id: str,
        product_id: str,
        variant_id: str,
        quantity: int,
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        product, variant = self._resolve_product_variant(product_id, variant_id)
        if not variant["inStock"]:
            raise HTTPException(status_code=409, detail="Variant is out of stock")

        with self.store.lock:
            existing = next(
                (
                    item
                    for item in cart["items"]
                    if item["productId"] == product_id and item["variantId"] == variant_id
                ),
                None,
            )
            if existing:
                existing["quantity"] += quantity
            else:
                item = {
                    "itemId": self.store.next_id("item"),
                    "productId": product["id"],
                    "variantId": variant["id"],
                    "name": product["name"],
                    "price": product["price"],
                    "quantity": quantity,
                    "image": product["images"][0],
                }
                cart["items"].append(item)
            self._recalculate_cart(cart)
            return deepcopy(cart)

    def update_item(
        self, user_id: str | None, session_id: str, item_id: str, quantity: int
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        with self.store.lock:
            target = next((item for item in cart["items"] if item["itemId"] == item_id), None)
            if not target:
                raise HTTPException(status_code=404, detail="Cart item not found")
            target["quantity"] = quantity
            self._recalculate_cart(cart)
            return deepcopy(cart)

    def remove_item(self, user_id: str | None, session_id: str, item_id: str) -> None:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        with self.store.lock:
            before = len(cart["items"])
            cart["items"] = [item for item in cart["items"] if item["itemId"] != item_id]
            if len(cart["items"]) == before:
                raise HTTPException(status_code=404, detail="Cart item not found")
            self._recalculate_cart(cart)

    def apply_discount(
        self, user_id: str | None, session_id: str, discount_code: str
    ) -> dict[str, Any]:
        cart = self._get_or_create_cart(user_id=user_id, session_id=session_id)
        normalized = discount_code.strip().upper()
        if normalized == "SAVE20":
            with self.store.lock:
                cart["appliedDiscount"] = {
                    "code": "SAVE20",
                    "type": "percentage",
                    "value": 20,
                }
                self._recalculate_cart(cart)
                return deepcopy(cart)
        raise HTTPException(status_code=400, detail="Invalid discount code")

    def attach_cart_to_user(self, session_id: str, user_id: str) -> None:
        with self.store.lock:
            session_cart = next(
                (c for c in self.store.carts_by_id.values() if c.get("sessionId") == session_id),
                None,
            )
            if not session_cart:
                return
            session_cart["userId"] = user_id
            self._recalculate_cart(session_cart)

    def _get_or_create_cart(self, user_id: str | None, session_id: str) -> dict[str, Any]:
        with self.store.lock:
            for cart in self.store.carts_by_id.values():
                if user_id and cart.get("userId") == user_id:
                    return cart
                if not user_id and cart.get("sessionId") == session_id and not cart.get("userId"):
                    return cart

            cart_id = self.store.next_id("cart")
            cart = {
                "id": cart_id,
                "userId": user_id,
                "sessionId": session_id,
                "items": [],
                "subtotal": 0.0,
                "tax": 0.0,
                "shipping": 0.0,
                "discount": 0.0,
                "total": 0.0,
                "itemCount": 0,
                "currency": "USD",
                "appliedDiscount": None,
                "createdAt": self.store.iso_now(),
                "updatedAt": self.store.iso_now(),
            }
            self.store.carts_by_id[cart_id] = cart
            return cart

    def _resolve_product_variant(
        self, product_id: str, variant_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        with self.store.lock:
            product = self.store.products_by_id.get(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            variant = next((v for v in product["variants"] if v["id"] == variant_id), None)
            if not variant:
                raise HTTPException(status_code=404, detail="Variant not found")
            return product, variant

    def _recalculate_cart(self, cart: dict[str, Any]) -> None:
        subtotal = sum(item["price"] * item["quantity"] for item in cart["items"])
        discount = 0.0
        applied = cart.get("appliedDiscount")
        if applied and applied.get("type") == "percentage":
            discount = round(subtotal * (applied["value"] / 100), 2)

        taxable_base = max(0.0, subtotal - discount)
        tax = round(taxable_base * self.settings.cart_tax_rate, 2)
        shipping = self.settings.default_shipping_fee if cart["items"] else 0.0
        total = round(taxable_base + tax + shipping, 2)

        cart["subtotal"] = round(subtotal, 2)
        cart["tax"] = tax
        cart["shipping"] = shipping
        cart["discount"] = discount
        cart["total"] = total
        cart["itemCount"] = sum(item["quantity"] for item in cart["items"])
        cart["updatedAt"] = self.store.iso_now()

