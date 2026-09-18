from fastapi.testclient import TestClient


def register(
    client: TestClient,
    email: str = "ananya@example.com",
    password: str = "correct-horse-battery-staple",
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Ananya", "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_login_and_me(client: TestClient) -> None:
    registered = register(client)
    assert registered["user"]["email"] == "ananya@example.com"
    assert registered["refresh_token"] not in registered["access_token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["display_name"] == "Ananya"

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ANANYA@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == registered["user"]["id"]


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "ANANYA@example.com",
            "display_name": "Someone else",
            "password": "another-secure-password",
        },
    )
    assert duplicate.status_code == 409


def test_refresh_token_is_rotated_and_old_token_is_rejected(client: TestClient) -> None:
    registered = register(client)
    old_refresh = registered["refresh_token"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != old_refresh

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


def test_invalid_access_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer definitely-not-valid"},
    )
    assert response.status_code == 401
