from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    jwt_claims,
    login_user,
    register_user,
    switch_organization,
)


async def test_register_and_login(client):
    await register_user(client, email="alice@example.com", username="alice")
    tokens = await login_user(client, email="alice@example.com")
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_login_includes_organization_claims(client):
    await register_user(client, email="claims@example.com", username="claims")
    tokens = await login_user(client, email="claims@example.com")
    claims = jwt_claims(tokens["access_token"])
    assert claims["organization_id"]
    assert claims["role"] == "OWNER"


async def test_create_organization(client):
    _, tokens = await create_authenticated_user(
        client, email="org@example.com", username="orguser"
    )
    organization = await create_organization(
        client, tokens["access_token"], name="Acme Corp", slug="acme-corp"
    )
    assert organization["name"] == "Acme Corp"
    assert organization["slug"] == "acme-corp"


async def test_list_organizations(client):
    user, tokens = await create_authenticated_user(
        client, email="list@example.com", username="listuser"
    )
    await create_organization(client, tokens["access_token"], name="Listed Org")
    response = await client.get("/v1/organizations", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    listed = next(item for item in data["items"] if item["name"] == "Listed Org")
    assert listed["role"] == "OWNER"
    assert all("role" in item for item in data["items"])


async def test_get_organization(client):
    _, tokens = await create_authenticated_user(
        client, email="get@example.com", username="getuser"
    )
    organization = await create_organization(
        client, tokens["access_token"], name="Get Org", slug="get-org"
    )
    response = await client.get(
        f"/v1/organizations/{organization['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["slug"] == "get-org"


async def test_update_organization(client):
    _, tokens = await create_authenticated_user(
        client, email="update@example.com", username="updateuser"
    )
    organization = await create_organization(
        client, tokens["access_token"], name="Old Name", slug="old-name"
    )
    response = await client.put(
        f"/v1/organizations/{organization['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "New Name", "description": "Updated"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_delete_organization(client):
    _, tokens = await create_authenticated_user(
        client, email="delete@example.com", username="deleteuser"
    )
    organization = await create_organization(
        client, tokens["access_token"], name="Delete Me", slug="delete-me"
    )
    response = await client.delete(
        f"/v1/organizations/{organization['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_organization_slug_conflict(client):
    _, tokens = await create_authenticated_user(
        client, email="slug@example.com", username="sluguser"
    )
    await create_organization(client, tokens["access_token"], name="First", slug="shared-slug")
    response = await client.post(
        "/v1/organizations",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Second", "slug": "shared-slug"},
    )
    assert response.status_code == 409


async def test_add_and_list_members(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="owner@example.com", username="owneruser"
    )
    member, _ = await create_authenticated_user(
        client, email="member@example.com", username="memberuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Team Org", slug="team-org"
    )
    add_response = await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": member["id"], "role": "DEVELOPER"},
    )
    assert add_response.status_code == 201

    list_response = await client.get(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert list_response.status_code == 200
    members = list_response.json()["items"]
    assert any(item["user_id"] == member["id"] for item in members)


async def test_remove_member(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="remove-owner@example.com", username="removeowner"
    )
    member, _ = await create_authenticated_user(
        client, email="remove-member@example.com", username="removemember"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Remove Org", slug="remove-org"
    )
    created = await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": member["id"], "role": "VIEWER"},
    )
    member_id = created.json()["id"]
    response = await client.delete(
        f"/v1/organizations/{organization['id']}/members/{member_id}",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_cannot_remove_last_owner(client):
    user, tokens = await create_authenticated_user(
        client, email="lastowner@example.com", username="lastowner"
    )
    organizations = await client.get(
        "/v1/organizations", headers=auth_headers(tokens["access_token"])
    )
    organization_id = organizations.json()["items"][0]["id"]
    members = await client.get(
        f"/v1/organizations/{organization_id}/members",
        headers=auth_headers(tokens["access_token"]),
    )
    owner_member = next(item for item in members.json()["items"] if item["user_id"] == user["id"])
    response = await client.delete(
        f"/v1/organizations/{organization_id}/members/{owner_member['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422


async def test_switch_organization_updates_jwt(client):
    user, tokens = await create_authenticated_user(
        client, email="switch@example.com", username="switchuser"
    )
    second_org = await create_organization(
        client, tokens["access_token"], name="Second Org", slug="second-org"
    )
    switched = await switch_organization(client, tokens["access_token"], second_org["id"])
    claims = jwt_claims(switched["access_token"])
    assert claims["organization_id"] == second_org["id"]
    assert claims["role"] == "OWNER"


async def test_non_member_cannot_get_organization(client):
    _, owner_tokens = await create_authenticated_user(
        client, email="private@example.com", username="privateowner"
    )
    _, outsider_tokens = await create_authenticated_user(
        client, email="outsider@example.com", username="outsider"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Private Org", slug="private-org"
    )
    response = await client.get(
        f"/v1/organizations/{organization['id']}",
        headers=auth_headers(outsider_tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_create_invitation(client):
    _, tokens = await create_authenticated_user(
        client, email="invite-owner@example.com", username="inviteowner"
    )
    organization = await create_organization(
        client, tokens["access_token"], name="Invite Org", slug="invite-org"
    )
    response = await client.post(
        "/v1/invitations",
        headers=auth_headers(tokens["access_token"]),
        json={
            "organization_id": organization["id"],
            "email": "newmember@example.com",
            "role": "DEVELOPER",
        },
    )
    assert response.status_code == 201
    assert response.json()["email"] == "newmember@example.com"


async def test_accept_invitation(client):
    _, owner_tokens = await create_authenticated_user(
        client, email="accept-owner@example.com", username="acceptowner"
    )
    invitee, _ = await create_authenticated_user(
        client, email="invitee@example.com", username="invitee"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Accept Org", slug="accept-org"
    )
    invitation = await client.post(
        "/v1/invitations",
        headers=auth_headers(owner_tokens["access_token"]),
        json={
            "organization_id": organization["id"],
            "email": invitee["email"],
            "role": "PROJECT_MANAGER",
        },
    )
    token = invitation.json()["token"]
    response = await client.post(
        "/v1/invitations/accept",
        headers=auth_headers((await login_user(client, email=invitee["email"]))["access_token"]),
        json={"token": token},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "PROJECT_MANAGER"


async def test_list_resend_and_revoke_invitations(client):
    _, owner_tokens = await create_authenticated_user(
        client, email="invite-mgmt@example.com", username="invitemgmt"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Invite Mgmt Org", slug="invite-mgmt-org"
    )
    created = await client.post(
        "/v1/invitations",
        headers=auth_headers(owner_tokens["access_token"]),
        json={
            "organization_id": organization["id"],
            "email": "pending@example.com",
            "role": "DEVELOPER",
        },
    )
    assert created.status_code == 201
    invitation_id = created.json()["id"]
    original_token = created.json()["token"]

    listed = await client.get(
        f"/v1/organizations/{organization['id']}/invitations",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["email"] == "pending@example.com"

    preview = await client.get(f"/v1/invitations/preview/{original_token}")
    assert preview.status_code == 200
    assert preview.json()["valid"] is True
    assert preview.json()["organization_name"] == "Invite Mgmt Org"

    resent = await client.post(
        f"/v1/invitations/{invitation_id}/resend",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert resent.status_code == 200
    assert resent.json()["token"] != original_token

    revoked = await client.delete(
        f"/v1/invitations/{invitation_id}",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert revoked.status_code == 204

    listed_after = await client.get(
        f"/v1/organizations/{organization['id']}/invitations",
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert listed_after.json()["total"] == 0


async def test_create_organization_duplicate_slug_returns_conflict(client):
    _, tokens = await create_authenticated_user(client, email="dup@example.com", username="dupuser")
    headers = auth_headers(tokens["access_token"])
    first = await client.post(
        "/v1/organizations",
        headers=headers,
        json={"name": "First Org", "slug": "nexora-demo-pilot"},
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/v1/organizations",
        headers=headers,
        json={"name": "Second Org", "slug": "nexora-demo-pilot"},
    )
    assert second.status_code == 409
    assert "already taken" in second.json()["detail"].lower()


async def test_create_organization_does_not_seed_pilot_enrollment_or_operations(client):
    from app.database.session import AsyncSessionLocal
    from app.repositories.pilot import PilotEnrollmentRepo, PilotLiveOperationRepo

    _, tokens = await create_authenticated_user(client, email="nopilot@example.com", username="nopilot")
    headers = auth_headers(tokens["access_token"])
    created = await client.post(
        "/v1/organizations",
        headers=headers,
        json={"name": "Nexora Demo Pilot", "slug": "nexora-demo-pilot-ui"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    org_id = body["id"]
    assert body["name"] == "Nexora Demo Pilot"
    switch_headers = auth_headers(body["context"]["access_token"])

    async with AsyncSessionLocal() as session:
        enrollment = await PilotEnrollmentRepo(session).get_for_org(org_id)
        assert enrollment is None
        ops = await PilotLiveOperationRepo(session).list_for_org(org_id)
        assert ops == []

    live_ops = await client.get("/v1/pilot/live-operations", headers=switch_headers)
    if live_ops.status_code == 200:
        assert live_ops.json().get("items", []) == []
