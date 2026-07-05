"""Organization service forbidden paths and validation edge cases."""

from __future__ import annotations

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    switch_organization,
)


async def test_viewer_cannot_update_organization(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="org-viewer-upd-owner@example.com", username="orgvupowner"
    )
    viewer, viewer_tokens = await create_authenticated_user(
        client, email="org-viewer-upd@example.com", username="orgvupviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Viewer Update Org", slug="viewer-upd-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_org = await switch_organization(
        client, viewer_tokens["access_token"], organization["id"]
    )
    response = await client.put(
        f"/v1/organizations/{organization['id']}",
        headers=auth_headers(viewer_org["access_token"]),
        json={"name": "Hacked"},
    )
    assert response.status_code == 403


async def test_admin_cannot_delete_organization(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="org-admin-del-owner@example.com", username="orgadelowner"
    )
    admin, admin_tokens = await create_authenticated_user(
        client, email="org-admin-del@example.com", username="orgadeladmin"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Admin Delete Org", slug="admin-del-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": admin["id"], "role": "ADMIN"},
    )
    admin_org = await switch_organization(client, admin_tokens["access_token"], organization["id"])
    response = await client.delete(
        f"/v1/organizations/{organization['id']}",
        headers=auth_headers(admin_org["access_token"]),
    )
    assert response.status_code == 403


async def test_admin_cannot_assign_owner_role(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="org-owner-role-owner@example.com", username="orgorowner"
    )
    admin, admin_tokens = await create_authenticated_user(
        client, email="org-owner-role-admin@example.com", username="orgoradmin"
    )
    target, _ = await create_authenticated_user(
        client, email="org-owner-role-target@example.com", username="orgortarget"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Owner Role Org", slug="owner-role-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": admin["id"], "role": "ADMIN"},
    )
    admin_org = await switch_organization(client, admin_tokens["access_token"], organization["id"])
    response = await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(admin_org["access_token"]),
        json={"user_id": target["id"], "role": "OWNER"},
    )
    assert response.status_code == 403


async def test_invite_existing_member_conflict(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="org-inv-member-owner@example.com", username="orgimowner"
    )
    member, _ = await create_authenticated_user(
        client, email="org-inv-member@example.com", username="orgimmember"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Invite Member Org", slug="invite-member-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": member["id"], "role": "DEVELOPER"},
    )
    response = await client.post(
        "/v1/invitations",
        headers=auth_headers(owner_tokens["access_token"]),
        json={
            "organization_id": organization["id"],
            "email": member["email"],
            "role": "DEVELOPER",
        },
    )
    assert response.status_code == 409


async def test_accept_invitation_wrong_email_forbidden(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="org-wrong-email-owner@example.com", username="orgweowner"
    )
    _, wrong_tokens = await create_authenticated_user(
        client, email="org-wrong-email-user@example.com", username="orgweuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Wrong Email Org", slug="wrong-email-org"
    )
    invitation = await client.post(
        "/v1/invitations",
        headers=auth_headers(owner_tokens["access_token"]),
        json={
            "organization_id": organization["id"],
            "email": "intended@example.com",
            "role": "DEVELOPER",
        },
    )
    token = invitation.json()["token"]
    response = await client.post(
        "/v1/invitations/accept",
        headers=auth_headers(wrong_tokens["access_token"]),
        json={"token": token},
    )
    assert response.status_code == 403


async def test_add_member_unknown_user_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="org-unknown-user@example.com", username="orgunkuser"
    )
    organization = await create_organization(
        client, tokens["access_token"], name="Unknown User Org", slug="unknown-user-org"
    )
    response = await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(tokens["access_token"]),
        json={"user_id": "00000000-0000-0000-0000-000000000000", "role": "DEVELOPER"},
    )
    assert response.status_code == 404


async def test_revoke_non_pending_invitation_fails(client):
    _, owner_tokens = await create_authenticated_user(
        client, email="org-revoke-owner@example.com", username="orgrevowner"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Revoke Org", slug="revoke-org"
    )
    created = await client.post(
        "/v1/invitations",
        headers=auth_headers(owner_tokens["access_token"]),
        json={
            "organization_id": organization["id"],
            "email": "revoke-me@example.com",
            "role": "DEVELOPER",
        },
    )
    invitation_id = created.json()["id"]
    await client.delete(
        f"/v1/invitations/{invitation_id}",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    response = await client.delete(
        f"/v1/invitations/{invitation_id}",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert response.status_code == 422
