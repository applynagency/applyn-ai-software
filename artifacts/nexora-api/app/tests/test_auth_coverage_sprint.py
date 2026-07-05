"""Auth service logout, conflict, and refresh edge cases."""

from __future__ import annotations

from app.tests.conftest import auth_headers, login_user, register_user


async def test_register_duplicate_email_conflict(client):
    await register_user(client, email="dup-email@example.com", username="dupemail1")
    response = await client.post(
        "/v1/auth/register",
        json={
            "email": "dup-email@example.com",
            "username": "dupemail2",
            "full_name": "Dup",
            "password": "password123",
        },
    )
    assert response.status_code == 409


async def test_register_duplicate_username_conflict(client):
    await register_user(client, email="dup-user-a@example.com", username="dupusername")
    response = await client.post(
        "/v1/auth/register",
        json={
            "email": "dup-user-b@example.com",
            "username": "dupusername",
            "full_name": "Dup",
            "password": "password123",
        },
    )
    assert response.status_code == 409


async def test_login_invalid_password_unauthorized(client):
    await register_user(client, email="bad-pass@example.com", username="badpass")
    response = await client.post(
        "/v1/auth/login",
        json={"email": "bad-pass@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


async def test_refresh_invalid_token_unauthorized(client):
    response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": "not-a-valid-token"},
    )
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await register_user(client, email="logout@example.com", username="logoutuser")
    tokens = await login_user(client, email="logout@example.com")
    logout = await client.post(
        "/v1/auth/logout",
        headers=auth_headers(tokens["access_token"]),
    )
    assert logout.status_code == 204
    refresh = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 401


async def test_deactivated_user_cannot_login(client):
    from app.database.session import AsyncSessionLocal
    from app.repositories.user import UserRepository

    await register_user(client, email="inactive@example.com", username="inactiveuser")
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email("inactive@example.com")
        assert user is not None
        user.is_active = False
        await session.commit()
    response = await client.post(
        "/v1/auth/login",
        json={"email": "inactive@example.com", "password": "password123"},
    )
    assert response.status_code == 401
    assert "deactivated" in response.text.lower()
