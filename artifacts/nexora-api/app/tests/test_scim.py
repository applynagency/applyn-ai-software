"""SCIM 2.0 tests — Users, Groups (role sync), PATCH, Bulk, deactivate/reactivate.

Exercises the real per-organization bearer-token auth, the org-scoped resource
lifecycle, SCIM PATCH (Okta + Entra shapes), Bulk, and group→role mapping wired
to the SSO role mappings.
"""

from __future__ import annotations

import pytest

from app.database.session import AsyncSessionLocal
from app.repositories.organization import OrganizationMemberRepository
from app.repositories.user import UserRepository

from .conftest import auth_headers, create_authenticated_user, create_organization

pytestmark = pytest.mark.asyncio


async def _make_superuser(email: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email(email)
        user.is_superuser = True
        session.add(user)
        await session.commit()


async def _superuser_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="scimadmin@example.com", username="scimadmin"
    )
    await _make_superuser("scimadmin@example.com")
    return tokens["access_token"]


async def _setup(client):
    su_token = await _superuser_token(client)
    org = await create_organization(client, su_token, name="Acme", slug="acme-scim")
    resp = await client.post(
        "/v1/scim/v2/admin/tokens",
        headers=auth_headers(su_token),
        json={"organization_id": org["id"], "name": "okta-prod"},
    )
    assert resp.status_code == 201, resp.text
    bearer = resp.json()["token"]
    assert bearer.startswith("scim_")
    return su_token, org, {"Authorization": f"Bearer {bearer}"}


async def _member_role(org_id: str, email: str) -> str | None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email(email)
        if not user:
            return None
        membership = await OrganizationMemberRepository(session).get_membership(
            org_id, user.id
        )
        return membership.role.value if membership else None


async def _user_active(email: str) -> bool | None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email(email)
        return user.is_active if user else None


async def _create_scim_user(client, headers, *, user_name, **extra) -> dict:
    body = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": user_name,
        "name": {"givenName": "Test", "familyName": "User"},
        "active": True,
    }
    body.update(extra)
    resp = await client.post("/v1/scim/v2/Users", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- auth -------------------------------------------------------------------


async def test_scim_requires_bearer_token(client):
    resp = await client.get("/v1/scim/v2/Users")
    assert resp.status_code == 401
    body = resp.json()
    assert body["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]


async def test_scim_rejects_invalid_token(client):
    await _setup(client)
    resp = await client.get(
        "/v1/scim/v2/Users", headers={"Authorization": "Bearer scim_wrong"}
    )
    assert resp.status_code == 401


async def test_admin_token_requires_superuser(client):
    _, tokens = await create_authenticated_user(
        client, email="plain@example.com", username="plainuser"
    )
    org = await create_organization(
        client, tokens["access_token"], name="P", slug="p-org"
    )
    resp = await client.post(
        "/v1/scim/v2/admin/tokens",
        headers=auth_headers(tokens["access_token"]),
        json={"organization_id": org["id"], "name": "x"},
    )
    assert resp.status_code == 403


# --- Users ------------------------------------------------------------------


async def test_create_and_get_user(client):
    _, org, headers = await _setup(client)
    created = await _create_scim_user(
        client, headers, user_name="alice@acme.com", externalId="ext-alice"
    )
    assert created["userName"] == "alice@acme.com"
    assert created["active"] is True
    assert created["externalId"] == "ext-alice"
    assert created["id"]

    got = await client.get(f"/v1/scim/v2/Users/{created['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["userName"] == "alice@acme.com"

    # Provisioned as an org member with the default role.
    assert await _member_role(org["id"], "alice@acme.com") == "VIEWER"


async def test_create_duplicate_user_conflicts(client):
    _, _, headers = await _setup(client)
    await _create_scim_user(client, headers, user_name="dup@acme.com")
    resp = await client.post(
        "/v1/scim/v2/Users",
        headers=headers,
        json={"userName": "dup@acme.com"},
    )
    assert resp.status_code == 409
    assert resp.json()["scimType"] == "uniqueness"


async def test_list_users_with_filter_and_pagination(client):
    _, _, headers = await _setup(client)
    await _create_scim_user(client, headers, user_name="a@acme.com")
    await _create_scim_user(client, headers, user_name="b@acme.com")

    listed = await client.get("/v1/scim/v2/Users?startIndex=1&count=10", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["totalResults"] == 2
    assert body["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]

    filtered = await client.get(
        '/v1/scim/v2/Users?filter=userName eq "a@acme.com"', headers=headers
    )
    assert filtered.json()["totalResults"] == 1
    assert filtered.json()["Resources"][0]["userName"] == "a@acme.com"


async def test_replace_user(client):
    _, _, headers = await _setup(client)
    created = await _create_scim_user(client, headers, user_name="carol@acme.com")
    resp = await client.put(
        f"/v1/scim/v2/Users/{created['id']}",
        headers=headers,
        json={
            "userName": "carol@acme.com",
            "name": {"givenName": "Carol", "familyName": "Jones"},
            "displayName": "Carol Jones",
            "active": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["displayName"] == "Carol Jones"


async def test_delete_user_deprovisions(client):
    _, org, headers = await _setup(client)
    created = await _create_scim_user(client, headers, user_name="del@acme.com")
    resp = await client.delete(f"/v1/scim/v2/Users/{created['id']}", headers=headers)
    assert resp.status_code == 204
    gone = await client.get(f"/v1/scim/v2/Users/{created['id']}", headers=headers)
    assert gone.status_code == 404
    # Global account deactivated once no longer SCIM-managed.
    assert await _user_active("del@acme.com") is False


# --- deactivate / reactivate ------------------------------------------------


async def test_deactivate_via_patch_entra_style(client):
    _, _, headers = await _setup(client)
    created = await _create_scim_user(client, headers, user_name="suspend@acme.com")
    # Microsoft Entra sends no path, value is an attribute bag.
    resp = await client.patch(
        f"/v1/scim/v2/Users/{created['id']}",
        headers=headers,
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "value": {"active": False}}],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False
    assert await _user_active("suspend@acme.com") is False


async def test_reactivate_via_patch_okta_style(client):
    _, _, headers = await _setup(client)
    created = await _create_scim_user(client, headers, user_name="back@acme.com")
    await client.patch(
        f"/v1/scim/v2/Users/{created['id']}",
        headers=headers,
        json={"Operations": [{"op": "replace", "path": "active", "value": False}]},
    )
    assert await _user_active("back@acme.com") is False

    resp = await client.patch(
        f"/v1/scim/v2/Users/{created['id']}",
        headers=headers,
        json={"Operations": [{"op": "replace", "path": "active", "value": True}]},
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is True
    assert await _user_active("back@acme.com") is True


# --- Groups + role mapping --------------------------------------------------


async def _create_role_mapping_connection(client, su_token, org_id):
    resp = await client.post(
        "/v1/auth/sso/connections",
        headers=auth_headers(su_token),
        json={
            "slug": "acme-roles",
            "display_name": "Acme roles",
            "protocol": "SAML",
            "provider": "GENERIC_SAML",
            "organization_id": org_id,
            "role_mappings": {"Engineers": "DEVELOPER", "Admins": "ADMIN"},
        },
    )
    assert resp.status_code == 201, resp.text


async def test_group_membership_sets_member_role(client):
    su_token, org, headers = await _setup(client)
    await _create_role_mapping_connection(client, su_token, org["id"])

    user = await _create_scim_user(client, headers, user_name="eng@acme.com")
    assert await _member_role(org["id"], "eng@acme.com") == "VIEWER"

    resp = await client.post(
        "/v1/scim/v2/Groups",
        headers=headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": "Engineers",
            "members": [{"value": user["id"]}],
        },
    )
    assert resp.status_code == 201, resp.text
    group = resp.json()
    assert group["displayName"] == "Engineers"
    assert len(group["members"]) == 1
    # Group role mapping applied to the org membership.
    assert await _member_role(org["id"], "eng@acme.com") == "DEVELOPER"


async def test_group_patch_add_and_remove_members(client):
    su_token, org, headers = await _setup(client)
    await _create_role_mapping_connection(client, su_token, org["id"])
    user = await _create_scim_user(client, headers, user_name="member@acme.com")

    group = (
        await client.post(
            "/v1/scim/v2/Groups",
            headers=headers,
            json={"displayName": "Admins"},
        )
    ).json()

    add = await client.patch(
        f"/v1/scim/v2/Groups/{group['id']}",
        headers=headers,
        json={
            "Operations": [
                {"op": "add", "path": "members", "value": [{"value": user["id"]}]}
            ]
        },
    )
    assert add.status_code == 200
    assert len(add.json()["members"]) == 1
    assert await _member_role(org["id"], "member@acme.com") == "ADMIN"

    remove = await client.patch(
        f"/v1/scim/v2/Groups/{group['id']}",
        headers=headers,
        json={
            "Operations": [
                {"op": "remove", "path": f'members[value eq "{user["id"]}"]'}
            ]
        },
    )
    assert remove.status_code == 200
    assert remove.json()["members"] == []


async def test_group_list_and_delete(client):
    _, _, headers = await _setup(client)
    created = (
        await client.post(
            "/v1/scim/v2/Groups", headers=headers, json={"displayName": "Temp"}
        )
    ).json()
    listed = await client.get("/v1/scim/v2/Groups", headers=headers)
    assert listed.json()["totalResults"] == 1
    deleted = await client.delete(f"/v1/scim/v2/Groups/{created['id']}", headers=headers)
    assert deleted.status_code == 204


# --- Bulk -------------------------------------------------------------------


async def test_bulk_create_users(client):
    _, _, headers = await _setup(client)
    resp = await client.post(
        "/v1/scim/v2/Bulk",
        headers=headers,
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:BulkRequest"],
            "Operations": [
                {
                    "method": "POST",
                    "path": "/Users",
                    "bulkId": "u1",
                    "data": {"userName": "bulk1@acme.com"},
                },
                {
                    "method": "POST",
                    "path": "/Users",
                    "bulkId": "u2",
                    "data": {"userName": "bulk2@acme.com"},
                },
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    ops = resp.json()["Operations"]
    assert len(ops) == 2
    assert all(o["status"] == "201" for o in ops)
    assert all("location" in o for o in ops)

    listed = await client.get("/v1/scim/v2/Users", headers=headers)
    assert listed.json()["totalResults"] == 2


async def test_bulk_reports_per_operation_errors(client):
    _, _, headers = await _setup(client)
    await _create_scim_user(client, headers, user_name="exists@acme.com")
    resp = await client.post(
        "/v1/scim/v2/Bulk",
        headers=headers,
        json={
            "Operations": [
                {"method": "POST", "path": "/Users", "data": {"userName": "exists@acme.com"}},
                {"method": "POST", "path": "/Users", "data": {"userName": "fresh@acme.com"}},
            ]
        },
    )
    assert resp.status_code == 200
    ops = resp.json()["Operations"]
    assert ops[0]["status"] == "409"
    assert ops[1]["status"] == "201"


# --- discovery --------------------------------------------------------------


async def test_service_provider_config(client):
    _, _, headers = await _setup(client)
    resp = await client.get("/v1/scim/v2/ServiceProviderConfig", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["patch"]["supported"] is True
    assert body["bulk"]["supported"] is True
    assert body["authenticationSchemes"][0]["type"] == "oauthbearertoken"
