from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_team,
    login_user,
    switch_organization,
)


async def test_project_manager_can_create_team(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="pm-owner@example.com", username="pmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="pm-user@example.com", username="pmuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="PM Org", slug="pm-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(
        client, (await login_user(client, email=pm["email"]))["access_token"],
        organization["id"],
    )
    team = await create_team(client, pm_tokens["access_token"], name="PM Team")
    assert team["name"] == "PM Team"


async def test_developer_cannot_create_team(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dev-owner@example.com", username="devowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="dev-user@example.com", username="devuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dev Org", slug="dev-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.post(
        "/v1/teams",
        headers=auth_headers(dev_tokens["access_token"]),
        json={"name": "Blocked", "team_type": "CUSTOM"},
    )
    assert response.status_code == 403


async def test_developer_can_view_teams(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dev-view-owner@example.com", username="devviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="dev-view@example.com", username="devview"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dev View Org", slug="dev-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    await create_team(client, owner_in_org["access_token"], name="Visible Team")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get("/v1/teams", headers=auth_headers(dev_tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_developer_cannot_delete_team(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dev-del-owner@example.com", username="devdelowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="dev-del@example.com", username="devdel"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dev Del Org", slug="dev-del-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    team = await create_team(client, owner_in_org["access_token"], name="Protected Team")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.delete(
        f"/v1/teams/{team['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 403


async def test_project_manager_cannot_delete_team(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="pm-del-owner@example.com", username="pmdelowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="pm-del@example.com", username="pmdel"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="PM Del Org", slug="pm-del-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    team = await create_team(client, owner_in_org["access_token"], name="PM Protected")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(
        client, (await login_user(client, email=pm["email"]))["access_token"],
        organization["id"],
    )
    response = await client.delete(
        f"/v1/teams/{team['id']}",
        headers=auth_headers(pm_tokens["access_token"]),
    )
    assert response.status_code == 403


async def test_admin_can_archive_team(client):
    _, tokens = await create_authenticated_user(
        client, email="archive-admin@example.com", username="archiveadmin"
    )
    team = await create_team(client, tokens["access_token"], name="Archive Me")
    response = await client.post(
        f"/v1/teams/{team['id']}/archive",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
