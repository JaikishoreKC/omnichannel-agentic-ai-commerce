from fastapi.testclient import TestClient

from app.main import app


def test_guest_cart_is_attached_after_login() -> None:
    client = TestClient(app)

    session_resp = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert session_resp.status_code == 201
    session_id = session_resp.json()["sessionId"]

    add_resp = client.post(
        "/v1/cart/items",
        json={"productId": "prod_003", "variantId": "var_005", "quantity": 2},
        headers={"X-Session-Id": session_id},
    )
    assert add_resp.status_code == 201

    register_resp = client.post(
        "/v1/auth/register",
        json={
            "email": "guest-transfer@example.com",
            "password": "SecurePass123!",
            "name": "Guest Transfer",
        },
        headers={"X-Session-Id": session_id},
    )
    assert register_resp.status_code == 201
    token = register_resp.json()["accessToken"]

    cart_resp = client.get(
        "/v1/cart",
        headers={"Authorization": f"Bearer {token}", "X-Session-Id": session_id},
    )
    assert cart_resp.status_code == 200
    assert cart_resp.json()["itemCount"] == 2
