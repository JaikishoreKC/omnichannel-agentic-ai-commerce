from fastapi.testclient import TestClient

from app.main import app


def test_recommendations_use_user_preferred_category() -> None:
    client = TestClient(app)

    session = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    register = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": "recommend-pref@example.com",
            "password": "SecurePass123!",
            "name": "Rec User",
        },
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    update_prefs = client.put(
        "/v1/memory/preferences",
        headers=headers,
        json={"categories": ["accessories"]},
    )
    assert update_prefs.status_code == 200

    recommend = client.post(
        "/v1/interactions/message",
        headers=headers,
        json={"sessionId": session_id, "content": "recommend something", "channel": "web"},
    )
    assert recommend.status_code == 200
    payload = recommend.json()["payload"]
    assert payload["agent"] == "product"
    products = payload["data"]["products"]
    assert len(products) >= 1
    assert all(item["category"] == "accessories" for item in products)
