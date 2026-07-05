from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_team,
    switch_organization,
)


async def test_team_isolated_between_organizations(client):
    user, tokens = await create_authenticated_user(
        client, email="team-iso@example.com", username="teamiso"
    )
    team = await create_team(client, tokens["access_token"], name="Org A Team")

    org_b = await create_organization(
        client, tokens["access_token"], name="Team Iso B", slug="team-iso-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])

    response = await client.get(
        f"/v1/teams/{team['id']}",
        headers=auth_headers(switched["access_token"]),
    )
    assert response.status_code == 404


async def test_team_list_scoped_to_organization(client):
    user, tokens = await create_authenticated_user(
        client, email="team-scope@example.com", username="teamscope"
    )
    await create_team(client, tokens["access_token"], name="Scoped Team A")

    org_b = await create_organization(
        client, tokens["access_token"], name="Team Scope B", slug="team-scope-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])
    await create_team(client, switched["access_token"], name="Scoped Team B")

    teams = await client.get("/v1/teams", headers=auth_headers(switched["access_token"]))
    names = {item["name"] for item in teams.json()["items"]}
    assert "Scoped Team B" in names
    assert "Scoped Team A" not in names


async def test_responsibility_isolated_between_organizations(client):
    user, tokens = await create_authenticated_user(
        client, email="resp-iso@example.com", username="respiso"
    )
    team = await create_team(client, tokens["access_token"])
    created = await client.post(
        f"/v1/teams/{team['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Secret task", "priority": "HIGH"},
    )

    org_b = await create_organization(
        client, tokens["access_token"], name="Resp Iso B", slug="resp-iso-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])

    response = await client.put(
        f"/v1/responsibilities/{created.json()['id']}",
        headers=auth_headers(switched["access_token"]),
        json={"title": "Hacked"},
    )
    assert response.status_code == 404


async def test_template_apply_scoped_to_active_organization(client):
    user, tokens = await create_authenticated_user(
        client, email="tpl-iso@example.com", username="tpliso"
    )
    default_org_id = (
        await client.get("/v1/organizations", headers=auth_headers(tokens["access_token"]))
    ).json()["items"][0]["id"]

    org_b = await create_organization(
        client, tokens["access_token"], name="Template Iso B", slug="template-iso-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])
    await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(switched["access_token"]),
        json={"template_slug": "crm-delivery"},
    )

    switched_back = await switch_organization(client, tokens["access_token"], default_org_id)
    teams = await client.get("/v1/teams", headers=auth_headers(switched_back["access_token"]))
    assert teams.json()["total"] == 0


async def test_viewer_cannot_create_team(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="team-viewer-owner@example.com", username="teamviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="team-viewer@example.com", username="teamviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Team Viewer Org", slug="team-viewer-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    from app.tests.conftest import login_user

    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.post(
        "/v1/teams",
        headers=auth_headers(viewer_tokens["access_token"]),
        json={"name": "Blocked Team", "team_type": "CUSTOM"},
    )
    assert response.status_code == 403
