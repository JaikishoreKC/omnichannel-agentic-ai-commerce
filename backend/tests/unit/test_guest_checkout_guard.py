from fastapi.testclient import TestClient

from app.main import app


def test_guest_can_add_to_cart_but_cannot_create_order() -> None:
    client = TestClient(app)

    session_resp = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert session_resp.status_code == 201
    session_id = session_resp.json()["sessionId"]

    add_resp = client.post(
        "/v1/cart/items",
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
        headers={"X-Session-Id": session_id},
    )
    assert add_resp.status_code == 201

    checkout_resp = client.post(
        "/v1/orders",
        json={
            "shippingAddress": {
                "name": "Jane Doe",
                "line1": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_test"},
        },
        headers={"Idempotency-Key": "test-key-1"},
    )
    assert checkout_resp.status_code == 401

