from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_session(client: TestClient, channel: str = "web") -> str:
    response = client.post("/v1/sessions", json={"channel": channel, "initialContext": {}})
    assert response.status_code == 201
    return response.json()["sessionId"]


def test_chat_memory_save_show_forget_and_clear() -> None:
    client = TestClient(app)
    session_id = _create_session(client)
    email = f"memory-{uuid4().hex}@example.com"

    register = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={"email": email, "password": "SecurePass123!", "name": "Memory User"},
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    save = client.post(
        "/v1/interactions/message",
        headers=headers,
        json={
            "sessionId": session_id,
            "content": "remember I like denim, prefer black, and my size is M",
            "channel": "web",
        },
    )
    assert save.status_code == 200
    save_payload = save.json()["payload"]
    assert save_payload["agent"] == "memory"

    prefs = client.get("/v1/memory/preferences", headers=headers)
    assert prefs.status_code == 200
    preferences = prefs.json()["preferences"]
    assert preferences["size"] == "m" or preferences["size"] == "M"
    assert "denim" in preferences["stylePreferences"]
    assert "black" in preferences["colorPreferences"]

    show = client.post(
        "/v1/interactions/message",
        headers=headers,
        json={"sessionId": session_id, "content": "what do you remember about me", "channel": "web"},
    )
    assert show.status_code == 200
    assert show.json()["payload"]["agent"] == "memory"
    assert len(show.json()["payload"]["data"]["highlights"]) >= 1

    forget = client.post(
        "/v1/interactions/message",
        headers=headers,
        json={"sessionId": session_id, "content": "forget denim", "channel": "web"},
    )
    assert forget.status_code == 200
    assert forget.json()["payload"]["agent"] == "memory"

    prefs_after_forget = client.get("/v1/memory/preferences", headers=headers)
    assert prefs_after_forget.status_code == 200
    assert "denim" not in prefs_after_forget.json()["preferences"]["stylePreferences"]

    clear = client.post(
        "/v1/interactions/message",
        headers=headers,
        json={"sessionId": session_id, "content": "clear my memory", "channel": "web"},
    )
    assert clear.status_code == 200
    assert clear.json()["payload"]["agent"] == "memory"

    prefs_after_clear = client.get("/v1/memory/preferences", headers=headers)
    assert prefs_after_clear.status_code == 200
    assert prefs_after_clear.json()["preferences"]["stylePreferences"] == []
    assert prefs_after_clear.json()["preferences"]["colorPreferences"] == []


def test_interaction_history_endpoint_returns_transcript_for_guest_session() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    first = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "show me running shoes", "channel": "web"},
    )
    assert first.status_code == 200

    second = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "add to cart", "channel": "web"},
    )
    assert second.status_code == 200

    history = client.get(f"/v1/interactions/history?sessionId={session_id}&limit=10")
    assert history.status_code == 200
    payload = history.json()
    assert payload["sessionId"] == session_id
    messages = payload["messages"]
    assert len(messages) >= 2
    assert any("running shoes" in str(row.get("message", "")).lower() for row in messages)
    assert all("response" in row for row in messages)


def test_login_merges_guest_cart_into_existing_user_cart() -> None:
    client = TestClient(app)
    session_a = _create_session(client, channel="web")
    email = f"merge-{uuid4().hex}@example.com"
    password = "SecurePass123!"

    register = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_a},
        json={"email": email, "password": password, "name": "Merge User"},
    )
    assert register.status_code == 201
    token_a = register.json()["accessToken"]
    auth_header_a = {"Authorization": f"Bearer {token_a}", "X-Session-Id": session_a}

    add_user_item = client.post(
        "/v1/cart/items",
        headers=auth_header_a,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_user_item.status_code == 201

    session_b = _create_session(client, channel="kiosk")
    add_guest_item = client.post(
        "/v1/cart/items",
        headers={"X-Session-Id": session_b},
        json={"productId": "prod_003", "variantId": "var_005", "quantity": 2},
    )
    assert add_guest_item.status_code == 201

    login = client.post(
        "/v1/auth/login",
        headers={"X-Session-Id": session_b},
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    canonical_session = login.json()["sessionId"]
    token_b = login.json()["accessToken"]

    cart = client.get(
        "/v1/cart",
        headers={"Authorization": f"Bearer {token_b}", "X-Session-Id": canonical_session},
    )
    assert cart.status_code == 200
    payload = cart.json()
    assert payload["itemCount"] == 3
    names = [str(item["name"]).lower() for item in payload["items"]]
    assert any("running shoes" in name for name in names)
    assert any("hoodie" in name for name in names)
