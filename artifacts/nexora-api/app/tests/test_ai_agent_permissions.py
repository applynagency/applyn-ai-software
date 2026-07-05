from app.tests.conftest import (
    auth_headers,
    create_ai_agent,
    create_authenticated_user,
    create_organization,
    create_workflow,
    create_workflow_stage,
    login_user,
    switch_organization,
)


async def test_project_manager_can_create_agent(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="agent-pm-owner@example.com", username="agentpmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="agent-pm-user@example.com", username="agentpmuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Agent PM Org", slug="agent-pm-org"
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
    agent = await create_ai_agent(client, pm_tokens["access_token"], name="PM Agent")
    assert agent["name"] == "PM Agent"


async def test_developer_cannot_create_agent(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="agent-dev-owner@example.com", username="agentdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="agent-dev-user@example.com", username="agentdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Agent Dev Org", slug="agent-dev-org"
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
        "/v1/ai-agents",
        headers=auth_headers(dev_tokens["access_token"]),
        json={"name": "Blocked Agent"},
    )
    assert response.status_code == 403


async def test_developer_can_view_agents(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="agent-dev-view-owner@example.com", username="agentdevviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="agent-dev-view@example.com", username="agentdevview"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Agent Dev View Org", slug="agent-dev-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    await create_ai_agent(client, owner_in_org["access_token"], name="Visible Agent")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get("/v1/ai-agents", headers=auth_headers(dev_tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_viewer_cannot_update_agent(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="agent-viewer-owner@example.com", username="agentviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="agent-viewer@example.com", username="agentviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Agent Viewer Org", slug="agent-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    agent = await create_ai_agent(client, owner_in_org["access_token"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.put(
        f"/v1/ai-agents/{agent['id']}",
        headers=auth_headers(viewer_tokens["access_token"]),
        json={"name": "Blocked Update"},
    )
    assert response.status_code == 403


async def test_developer_cannot_assign_agent(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="agent-dev-assign-owner@example.com", username="agentdevassignowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="agent-dev-assign@example.com", username="agentdevassign"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Agent Dev Assign Org", slug="agent-dev-assign-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    agent = await create_ai_agent(client, owner_in_org["access_token"])
    workflow = await create_workflow(client, owner_in_org["access_token"])
    stage = await create_workflow_stage(client, owner_in_org["access_token"], workflow["id"])
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
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(dev_tokens["access_token"]),
        json={"workflow_stage_id": stage["id"]},
    )
    assert response.status_code == 403
