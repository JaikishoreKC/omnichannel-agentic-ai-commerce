from fastapi.testclient import TestClient

from app.main import app


def _create_session(client: TestClient) -> str:
    response = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert response.status_code == 201
    return response.json()["sessionId"]


def test_interaction_search_and_add_to_cart_guest() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    search = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "Show me running shoes under $150",
            "channel": "web",
        },
    )
    assert search.status_code == 200
    payload = search.json()["payload"]
    assert payload["agent"] == "product"
    assert len(payload["data"]["products"]) >= 1

    add = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "add to cart", "channel": "web"},
    )
    assert add.status_code == 200
    assert add.json()["payload"]["agent"] == "cart"

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert cart.json()["itemCount"] >= 1


def test_interaction_checkout_requires_auth_then_succeeds() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    search = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "show me running shoes", "channel": "web"},
    )
    assert search.status_code == 200

    add = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "add to cart", "channel": "web"},
    )
    assert add.status_code == 200

    guest_checkout = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "checkout", "channel": "web"},
    )
    assert guest_checkout.status_code == 200
    assert guest_checkout.json()["payload"]["data"]["code"] == "AUTH_REQUIRED"

    auth = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": "interaction-checkout@example.com",
            "password": "SecurePass123!",
            "name": "Interaction User",
        },
    )
    assert auth.status_code == 201
    token = auth.json()["accessToken"]

    user_checkout = client.post(
        "/v1/interactions/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"sessionId": session_id, "content": "checkout", "channel": "web"},
    )
    assert user_checkout.status_code == 200
    payload = user_checkout.json()["payload"]
    assert payload["agent"] == "order"
    assert payload["data"]["order"]["status"] == "confirmed"


def test_interaction_parallel_multi_status() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    auth = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": "parallel-status@example.com",
            "password": "SecurePass123!",
            "name": "Parallel User",
        },
    )
    assert auth.status_code == 201
    token = auth.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}"}

    client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={"sessionId": session_id, "content": "show me running shoes", "channel": "web"},
    )
    client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={"sessionId": session_id, "content": "add to cart", "channel": "web"},
    )
    client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={"sessionId": session_id, "content": "checkout", "channel": "web"},
    )

    combined = client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={
            "sessionId": session_id,
            "content": "show my cart and order status",
            "channel": "web",
        },
    )
    assert combined.status_code == 200
    payload = combined.json()["payload"]
    assert payload["agent"] == "orchestrator"
    assert "cart" in payload["data"]
    assert "order" in payload["data"]

