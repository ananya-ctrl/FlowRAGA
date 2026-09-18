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
    assert "refresh_token" not in registered
    assert client.cookies.get("flowraga_refresh")
    assert client.cookies.get("flowraga_csrf") == registered["csrf_token"]

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


def test_refresh_cookie_is_httponly(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "cookie@example.com",
            "display_name": "Cookie Test",
            "password": "correct-horse-battery-staple",
        },
    )
    cookies = response.headers.get_list("set-cookie")
    refresh_cookie = next(cookie for cookie in cookies if cookie.startswith("flowraga_refresh="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("flowraga_csrf="))

    assert "HttpOnly" in refresh_cookie
    assert "SameSite=lax" in refresh_cookie
    assert "HttpOnly" not in csrf_cookie


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
    old_refresh = client.cookies.get("flowraga_refresh")
    assert old_refresh

    refreshed = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": registered["csrf_token"]},
    )
    assert refreshed.status_code == 200
    assert client.cookies.get("flowraga_refresh") != old_refresh

    client.cookies.set("flowraga_refresh", old_refresh)
    replay = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": refreshed.json()["csrf_token"]},
    )
    assert replay.status_code == 401


def test_refresh_requires_csrf_header(client: TestClient) -> None:
    register(client)
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 403


def test_logout_revokes_session_and_clears_cookies(client: TestClient) -> None:
    registered = register(client)
    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": registered["csrf_token"]},
    )
    assert response.status_code == 204
    assert client.cookies.get("flowraga_refresh") is None
    assert client.cookies.get("flowraga_csrf") is None


def test_invalid_access_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer definitely-not-valid"},
    )
    assert response.status_code == 401
