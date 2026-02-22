from fastapi.testclient import TestClient

from app.main import app


def test_websocket_message_flow() -> None:
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"channel": "websocket", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        websocket.send_json(
            {
                "type": "message",
                "payload": {"content": "show me running shoes", "timestamp": "2026-01-01T00:00:00Z"},
            }
        )
        response = websocket.receive_json()
        assert response["type"] == "response"
        assert response["payload"]["agent"] == "product"
        assert len(response["payload"]["data"]["products"]) >= 1

        websocket.send_json({"type": "typing", "payload": {"isTyping": True}})
        typing = websocket.receive_json()
        assert typing["type"] == "typing"
        assert typing["payload"]["isTyping"] is True

