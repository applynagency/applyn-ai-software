from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_team,
    create_workflow,
    create_workflow_stage,
    login_user,
    switch_organization,
)


async def test_project_manager_can_create_workflow(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="wf-pm-owner@example.com", username="wfpmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="wf-pm-user@example.com", username="wfpmuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="WF PM Org", slug="wf-pm-org"
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
    workflow = await create_workflow(client, pm_tokens["access_token"], name="PM Workflow")
    assert workflow["name"] == "PM Workflow"


async def test_developer_cannot_create_workflow(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="wf-dev-owner@example.com", username="wfdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="wf-dev-user@example.com", username="wfdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="WF Dev Org", slug="wf-dev-org"
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
        "/v1/workflows",
        headers=auth_headers(dev_tokens["access_token"]),
        json={"name": "Blocked Workflow"},
    )
    assert response.status_code == 403


async def test_developer_can_view_workflows(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="wf-dev-view-owner@example.com", username="wfdevviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="wf-dev-view@example.com", username="wfdevview"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="WF Dev View Org", slug="wf-dev-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    await create_workflow(client, owner_in_org["access_token"], name="Visible Workflow")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get("/v1/workflows", headers=auth_headers(dev_tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_viewer_cannot_update_workflow(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="wf-viewer-owner@example.com", username="wfviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="wf-viewer@example.com", username="wfviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="WF Viewer Org", slug="wf-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workflow = await create_workflow(client, owner_in_org["access_token"])
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
        f"/v1/workflows/{workflow['id']}",
        headers=auth_headers(viewer_tokens["access_token"]),
        json={"name": "Blocked Update"},
    )
    assert response.status_code == 403


async def test_developer_cannot_assign_team(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="wf-dev-assign-owner@example.com", username="wfdevassignowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="wf-dev-assign@example.com", username="wfdevassign"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="WF Dev Assign Org", slug="wf-dev-assign-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workflow = await create_workflow(client, owner_in_org["access_token"])
    stage = await create_workflow_stage(client, owner_in_org["access_token"], workflow["id"])
    team = await create_team(client, owner_in_org["access_token"])
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
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(dev_tokens["access_token"]),
        json={"team_id": team["id"]},
    )
    assert response.status_code == 403
