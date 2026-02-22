from fastapi.testclient import TestClient

from app.main import app


def _admin_headers(client: TestClient) -> dict[str, str]:
    admin_login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert admin_login.status_code == 200
    token = admin_login.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_update_inventory_and_product_stock_flag() -> None:
    client = TestClient(app)
    headers = _admin_headers(client)

    current = client.get("/v1/admin/inventory/var_001", headers=headers)
    assert current.status_code == 200
    assert "inventory" in current.json()

    update = client.put(
        "/v1/admin/inventory/var_001",
        headers=headers,
        json={"totalQuantity": 20, "availableQuantity": 0},
    )
    assert update.status_code == 200
    assert update.json()["inventory"]["availableQuantity"] == 0

    product = client.get("/v1/products/prod_001")
    assert product.status_code == 200
    variant = next(v for v in product.json()["variants"] if v["id"] == "var_001")
    assert variant["inStock"] is False

    restore = client.put(
        "/v1/admin/inventory/var_001",
        headers=headers,
        json={"availableQuantity": 5},
    )
    assert restore.status_code == 200
    assert restore.json()["inventory"]["availableQuantity"] == 5


def test_support_escalation_creates_ticket_and_stats_reflect_it() -> None:
    client = TestClient(app)

    session = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    escalation = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "I need a human agent to help with my order issue",
            "channel": "web",
        },
    )
    assert escalation.status_code == 200
    payload = escalation.json()["payload"]
    assert payload["agent"] == "support"
    assert payload["data"]["ticket"]["status"] == "open"

    admin_stats = client.get("/v1/admin/stats", headers=_admin_headers(client))
    assert admin_stats.status_code == 200
    assert admin_stats.json()["supportOpenTickets"] >= 1
