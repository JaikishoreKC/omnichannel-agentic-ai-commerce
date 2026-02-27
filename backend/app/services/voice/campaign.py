from __future__ import annotations
from typing import Any

def build_campaign_payload(
    *,
    user: dict[str, Any],
    cart: dict[str, Any],
    settings: dict[str, Any],
    default_template: str,
) -> dict[str, Any]:
    name = str(user.get("name", "")).strip() or "there"
    item_count = int(cart.get("itemCount", 0))
    cart_total = float(cart.get("total", 0.0))
    template = str(settings.get("scriptTemplate", "")).strip() or default_template
    try:
        script = template.format(name=name, item_count=item_count, cart_total=cart_total)
    except (KeyError, ValueError, TypeError):
        script = (
            f"Hi {name}, you still have {item_count} item(s) in your cart worth "
            f"${cart_total:.2f}. Would you like help checking out?"
        )
    
    items = []
    for row in cart.get("items", []):
        if not isinstance(row, dict):
            continue
        items.append(
            {
                "itemId": str(row.get("itemId", "")),
                "productId": str(row.get("productId", "")),
                "variantId": str(row.get("variantId", "")),
                "name": str(row.get("name", "")),
                "quantity": int(row.get("quantity", 0)),
            }
        )
    
    return {
        "scriptVersion": str(settings.get("scriptVersion", "v1")),
        "scriptText": script,
        "cart": {
            "id": str(cart.get("id", "")),
            "itemCount": item_count,
            "total": round(cart_total, 2),
            "currency": str(cart.get("currency", "USD")),
            "items": items,
        },
        "customer": {
            "id": str(user.get("id", "")),
            "name": name,
            "email": str(user.get("email", "")),
            "timezone": str(user.get("timezone", "")).strip()
            or str(settings.get("defaultTimezone", "UTC")),
        },
    }
