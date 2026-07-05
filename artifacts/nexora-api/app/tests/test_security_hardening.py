from app.database.session import AsyncSessionLocal
from app.models.organization import OrganizationRole
from app.repositories.organization import OrganizationMemberRepository
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_workflow,
    create_workspace,
    jwt_claims,
    login_user,
    switch_organization,
)


async def _add_org_member(client, owner_token, organization_id, user_id, role):
    return await client.post(
        f"/v1/organizations/{organization_id}/members",
        headers=auth_headers(owner_token),
        json={"user_id": user_id, "role": role},
    )


async def _set_member_role(organization_id: str, user_id: str, role: OrganizationRole) -> None:
    async with AsyncSessionLocal() as session:
        member_repo = OrganizationMemberRepository(session)
        membership = await member_repo.get_membership(organization_id, user_id)
        assert membership is not None
        await member_repo.update(membership, role=role)
        await session.commit()


async def test_admin_cannot_assign_owner_role_via_member_add(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="h2-owner@example.com", username="h2owner"
    )
    admin, _ = await create_authenticated_user(
        client, email="h2-admin@example.com", username="h2admin"
    )
    target, _ = await create_authenticated_user(
        client, email="h2-target@example.com", username="h2target"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="H2 Org", slug="h2-org"
    )
    admin_add = await _add_org_member(
        client,
        owner_tokens["access_token"],
        organization["id"],
        admin["id"],
        "ADMIN",
    )
    assert admin_add.status_code == 201

    admin_login = await login_user(client, email=admin["email"])
    admin_tokens = await switch_organization(
        client, admin_login["access_token"], organization["id"]
    )

    response = await _add_org_member(
        client,
        admin_tokens["access_token"],
        organization["id"],
        target["id"],
        "OWNER",
    )
    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()


async def test_admin_cannot_invite_owner_role(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="h2-invite-owner@example.com", username="h2inviteowner"
    )
    admin, _ = await create_authenticated_user(
        client, email="h2-invite-admin@example.com", username="h2inviteadmin"
    )
    organization = await create_organization(
        client,
        owner_tokens["access_token"],
        name="H2 Invite Org",
        slug="h2-invite-org",
    )
    assert (
        await _add_org_member(
            client,
            owner_tokens["access_token"],
            organization["id"],
            admin["id"],
            "ADMIN",
        )
    ).status_code == 201

    admin_login = await login_user(client, email=admin["email"])
    admin_tokens = await switch_organization(
        client, admin_login["access_token"], organization["id"]
    )

    response = await client.post(
        "/v1/invitations",
        headers=auth_headers(admin_tokens["access_token"]),
        json={
            "organization_id": organization["id"],
            "email": "future-owner@example.com",
            "role": "OWNER",
        },
    )
    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()


async def test_owner_can_assign_owner_role(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="h2-owner-ok@example.com", username="h2ownerok"
    )
    target, _ = await create_authenticated_user(
        client, email="h2-coowner@example.com", username="h2coowner"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="H2 Owner OK", slug="h2-owner-ok"
    )

    response = await _add_org_member(
        client,
        owner_tokens["access_token"],
        organization["id"],
        target["id"],
        "OWNER",
    )
    assert response.status_code == 201
    assert response.json()["role"] == "OWNER"


async def test_stale_jwt_role_uses_database_role(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="h3-owner@example.com", username="h3owner"
    )
    admin, _ = await create_authenticated_user(
        client, email="h3-admin@example.com", username="h3admin"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="H3 Org", slug="h3-org"
    )
    assert (
        await _add_org_member(
            client,
            owner_tokens["access_token"],
            organization["id"],
            admin["id"],
            "ADMIN",
        )
    ).status_code == 201

    admin_login = await login_user(client, email=admin["email"])
    admin_tokens = await switch_organization(
        client, admin_login["access_token"], organization["id"]
    )
    claims = jwt_claims(admin_tokens["access_token"])
    assert claims["role"] == "ADMIN"

    await _set_member_role(organization["id"], admin["id"], OrganizationRole.VIEWER)

    response = await client.post(
        "/v1/workspaces",
        headers=auth_headers(admin_tokens["access_token"]),
        json={"name": "Should Fail", "slug": "should-fail"},
    )
    assert response.status_code == 403


async def test_revoked_membership_rejects_protected_request(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="h3-revoke-owner@example.com", username="h3revokeowner"
    )
    member, _ = await create_authenticated_user(
        client, email="h3-revoke-member@example.com", username="h3revokemember"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="H3 Revoke Org", slug="h3-revoke-org"
    )
    created = await _add_org_member(
        client,
        owner_tokens["access_token"],
        organization["id"],
        member["id"],
        "DEVELOPER",
    )
    assert created.status_code == 201
    member_id = created.json()["id"]

    member_login = await login_user(client, email=member["email"])
    member_tokens = await switch_organization(
        client, member_login["access_token"], organization["id"]
    )

    removed = await client.delete(
        f"/v1/organizations/{organization['id']}/members/{member_id}",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert removed.status_code == 204

    response = await client.get(
        "/v1/workspaces",
        headers=auth_headers(member_tokens["access_token"]),
    )
    assert response.status_code == 401
    assert "membership" in response.json()["detail"].lower()


async def test_cross_tenant_workflow_returns_not_found(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="h8-wf-a@example.com", username="h8wfa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="h8-wf-b@example.com", username="h8wfb"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="H8 Org A", slug="h8-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="H8 Org B", slug="h8-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    workflow = await create_workflow(client, tokens_a_org["access_token"], name="H8 Workflow")

    response = await client.get(
        f"/v1/workflows/{workflow['id']}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cross_tenant_workspace_returns_not_found(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="h8-ws-a@example.com", username="h8wsa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="h8-ws-b@example.com", username="h8wsb"
    )
    workspace = await create_workspace(client, tokens_a["access_token"], slug="h8-ws")

    response = await client.get(
        f"/v1/workspaces/{workspace['id']}",
        headers=auth_headers(tokens_b["access_token"]),
    )
    assert response.status_code == 404
