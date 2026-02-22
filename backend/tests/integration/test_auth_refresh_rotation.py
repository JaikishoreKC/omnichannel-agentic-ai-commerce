from fastapi.testclient import TestClient

from app.main import app


def test_refresh_token_rotation_revokes_previous_token() -> None:
    client = TestClient(app)
    register = client.post(
        "/v1/auth/register",
        json={
            "email": "rotation@example.com",
            "password": "SecurePass123!",
            "name": "Rotation User",
        },
    )
    assert register.status_code == 201
    first_refresh = register.json()["refreshToken"]

    refreshed = client.post("/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert refreshed.status_code == 200
    second_refresh = refreshed.json()["refreshToken"]
    assert second_refresh != first_refresh

    reused = client.post("/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert reused.status_code == 401

    second = client.post("/v1/auth/refresh", json={"refreshToken": second_refresh})
    assert second.status_code == 200

