from datetime import UTC, datetime, timedelta

from jose import jwt

from app.core.config import settings
from app.core.security import decode_token
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    jwt_claims,
    switch_organization,
)


def _create_expired_access_token(
    user_id: str,
    *,
    organization_id: str,
    role: str = "OWNER",
) -> str:
    expire = datetime.now(UTC) - timedelta(minutes=5)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
        "organization_id": organization_id,
        "role": role,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def test_refresh_preserves_switched_organization(client):
    user, tokens = await create_authenticated_user(
        client, email="refresh-org@example.com", username="refreshorg"
    )
    default_org_id = jwt_claims(tokens["access_token"])["organization_id"]
    org_b = await create_organization(
        client, tokens["access_token"], name="Refresh Org B", slug="refresh-org-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])
    assert jwt_claims(switched["access_token"])["organization_id"] == org_b["id"]

    refresh_payload = decode_token(switched["refresh_token"])
    assert refresh_payload.get("organization_id") == org_b["id"]

    refreshed = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": switched["refresh_token"]},
    )
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["organization_id"] == org_b["id"]
    assert body["role"] == "OWNER"
    assert jwt_claims(body["access_token"])["organization_id"] == org_b["id"]
    assert jwt_claims(body["access_token"])["organization_id"] != default_org_id


async def test_refresh_honors_explicit_organization_id(client):
    user, tokens = await create_authenticated_user(
        client, email="refresh-explicit@example.com", username="refreshexplicit"
    )
    org_b = await create_organization(
        client, tokens["access_token"], name="Explicit Org B", slug="explicit-org-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])

    refreshed = await client.post(
        "/v1/auth/refresh",
        json={
            "refresh_token": switched["refresh_token"],
            "organization_id": org_b["id"],
        },
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["organization_id"] == org_b["id"]


async def test_expired_access_token_recovered_via_refresh(client):
    user, tokens = await create_authenticated_user(
        client, email="expired-flow@example.com", username="expiredflow"
    )
    org_id = jwt_claims(tokens["access_token"])["organization_id"]
    expired_access = _create_expired_access_token(user["id"], organization_id=org_id)

    expired_response = await client.get(
        "/v1/workspaces",
        headers=auth_headers(expired_access),
    )
    assert expired_response.status_code == 401

    refreshed = await client.post(
        "/v1/auth/refresh",
        json={
            "refresh_token": tokens["refresh_token"],
            "organization_id": org_id,
        },
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]

    recovered = await client.get(
        "/v1/workspaces",
        headers=auth_headers(new_access),
    )
    assert recovered.status_code == 200


async def test_refresh_token_recovery_after_org_switch(client):
    user, tokens = await create_authenticated_user(
        client, email="recovery-switch@example.com", username="recoveryswitch"
    )
    org_b = await create_organization(
        client, tokens["access_token"], name="Recovery Org B", slug="recovery-org-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])
    expired_access = _create_expired_access_token(
        user["id"],
        organization_id=org_b["id"],
        role="OWNER",
    )

    assert (
        await client.get("/v1/teams", headers=auth_headers(expired_access))
    ).status_code == 401

    refreshed = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": switched["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["organization_id"] == org_b["id"]

    teams = await client.get(
        "/v1/teams",
        headers=auth_headers(refreshed.json()["access_token"]),
    )
    assert teams.status_code == 200
