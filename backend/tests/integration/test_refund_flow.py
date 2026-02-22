from fastapi.testclient import TestClient

from app.main import app


def _register_and_get_token(client: TestClient, email: str) -> str:
    register = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "name": "Refund User",
        },
    )
    assert register.status_code == 201
    return register.json()["accessToken"]


def _create_order(client: TestClient, token: str, idempotency_key: str) -> str:
    auth_header = {"Authorization": f"Bearer {token}"}
    add_item = client.post(
        "/v1/cart/items",
        headers=auth_header,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201

    order = client.post(
        "/v1/orders",
        headers={**auth_header, "Idempotency-Key": idempotency_key},
        json={
            "shippingAddress": {
                "name": "Refund User",
                "line1": "100 Main St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_refund"},
        },
    )
    assert order.status_code == 201
    return order.json()["order"]["id"]


def test_refund_endpoint_marks_order_as_refunded() -> None:
    client = TestClient(app)
    token = _register_and_get_token(client, "refund-endpoint@example.com")
    order_id = _create_order(client, token, "refund-endpoint-key")
    auth_header = {"Authorization": f"Bearer {token}"}

    refund = client.post(
        f"/v1/orders/{order_id}/refund",
        headers=auth_header,
        json={"reason": "Item did not fit"},
    )
    assert refund.status_code == 200
    payload = refund.json()
    assert payload["status"] == "refunded"

    order = client.get(f"/v1/orders/{order_id}", headers=auth_header)
    assert order.status_code == 200
    order_payload = order.json()
    assert order_payload["status"] == "refunded"
    assert order_payload["payment"]["status"] == "refunded"


def test_chat_refund_intent_uses_order_agent() -> None:
    client = TestClient(app)
    token = _register_and_get_token(client, "refund-chat@example.com")
    order_id = _create_order(client, token, "refund-chat-key")
    auth_header = {"Authorization": f"Bearer {token}"}

    refund = client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={
            "sessionId": "session_999999",
            "content": f"please refund order {order_id}",
            "channel": "web",
        },
    )
    assert refund.status_code == 200
    payload = refund.json()["payload"]
    assert payload["agent"] == "order"
    assert payload["data"]["status"] == "refunded"
