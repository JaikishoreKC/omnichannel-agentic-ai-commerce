from fastapi.testclient import TestClient

from app.main import app


def test_orders_create_returns_201_for_authenticated_user() -> None:
    client = TestClient(app)

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "orders-contract@example.com",
            "password": "SecurePass123!",
            "name": "Orders Contract",
        },
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}"}

    add_item = client.post(
        "/v1/cart/items",
        headers=auth_header,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201

    order = client.post(
        "/v1/orders",
        headers={**auth_header, "Idempotency-Key": "orders-contract-key-1"},
        json={
            "shippingAddress": {
                "name": "Order User",
                "line1": "100 Market St",
                "city": "San Francisco",
                "state": "CA",
                "postalCode": "94102",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_contract"},
        },
    )
    assert order.status_code == 201
    body = order.json()
    assert "order" in body
    assert body["order"]["status"] == "confirmed"


def test_auth_required_and_validation_errors_use_standard_error_envelope() -> None:
    client = TestClient(app)

    unauthorized = client.post(
        "/v1/orders",
        headers={"Idempotency-Key": "orders-contract-key-guest"},
        json={
            "shippingAddress": {
                "name": "Guest",
                "line1": "1 Main St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_guest"},
        },
    )
    assert unauthorized.status_code == 401
    unauthorized_error = unauthorized.json()["error"]
    assert unauthorized_error["code"] == "AUTH_REQUIRED"
    assert isinstance(unauthorized_error.get("details"), list)

    invalid_register = client.post(
        "/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "short",
            "name": "x",
        },
    )
    assert invalid_register.status_code == 400
    validation_error = invalid_register.json()["error"]
    assert validation_error["code"] == "VALIDATION_ERROR"
    assert isinstance(validation_error.get("details"), list)
    assert len(validation_error["details"]) >= 1


def test_order_shipping_address_update_endpoint() -> None:
    client = TestClient(app)

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "orders-address-update@example.com",
            "password": "SecurePass123!",
            "name": "Orders Address",
        },
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}"}

    add_item = client.post(
        "/v1/cart/items",
        headers=auth_header,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201

    order = client.post(
        "/v1/orders",
        headers={**auth_header, "Idempotency-Key": "orders-address-key-1"},
        json={
            "shippingAddress": {
                "name": "Order User",
                "line1": "100 Market St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_address_contract"},
        },
    )
    assert order.status_code == 201
    order_id = order.json()["order"]["id"]

    update = client.put(
        f"/v1/orders/{order_id}/shipping-address",
        headers=auth_header,
        json={
            "shippingAddress": {
                "name": "Order User",
                "line1": "500 Main St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78702",
                "country": "US",
            }
        },
    )
    assert update.status_code == 200
    assert update.json()["shippingAddress"]["line1"] == "500 Main St"


def test_order_shipping_address_update_rejected_after_refund() -> None:
    client = TestClient(app)

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "orders-address-update-refund@example.com",
            "password": "SecurePass123!",
            "name": "Orders Address Refund",
        },
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}"}

    add_item = client.post(
        "/v1/cart/items",
        headers=auth_header,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201

    order = client.post(
        "/v1/orders",
        headers={**auth_header, "Idempotency-Key": "orders-address-key-2"},
        json={
            "shippingAddress": {
                "name": "Order User",
                "line1": "100 Market St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_address_contract_2"},
        },
    )
    assert order.status_code == 201
    order_id = order.json()["order"]["id"]

    refund = client.post(
        f"/v1/orders/{order_id}/refund",
        headers=auth_header,
        json={"reason": "Testing guardrail"},
    )
    assert refund.status_code == 200

    update = client.put(
        f"/v1/orders/{order_id}/shipping-address",
        headers=auth_header,
        json={
            "shippingAddress": {
                "name": "Order User",
                "line1": "500 Main St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78702",
                "country": "US",
            }
        },
    )
    assert update.status_code == 409
