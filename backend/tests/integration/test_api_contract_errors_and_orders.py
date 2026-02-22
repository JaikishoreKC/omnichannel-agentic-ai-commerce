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
