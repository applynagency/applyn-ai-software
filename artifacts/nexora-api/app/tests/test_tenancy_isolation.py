from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_product_owner_output,
    switch_organization,
)


async def test_workspace_list_scoped_to_active_organization(client):
    user, tokens = await create_authenticated_user(
        client, email="scope-a@example.com", username="scopea"
    )
    org_a = (await client.get("/v1/organizations", headers=auth_headers(tokens["access_token"]))).json()[
        "items"
    ][0]
    await create_workspace(client, tokens["access_token"], name="Org A Workspace", slug="org-a-ws")

    org_b = await create_organization(
        client, tokens["access_token"], name="Org B", slug="org-b-scope"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])
    await create_workspace(client, switched["access_token"], name="Org B Workspace", slug="org-b-ws")

    workspaces = await client.get(
        "/v1/workspaces", headers=auth_headers(switched["access_token"])
    )
    assert workspaces.status_code == 200
    names = {item["name"] for item in workspaces.json()["items"]}
    assert "Org B Workspace" in names
    assert "Org A Workspace" not in names


async def test_cannot_access_workspace_from_other_organization(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="iso-a@example.com", username="isoa"
    )
    workspace = await create_workspace(client, tokens_a["access_token"], slug="iso-ws")

    _, tokens_b = await create_authenticated_user(
        client, email="iso-b@example.com", username="isob"
    )
    response = await client.get(
        f"/v1/workspaces/{workspace['id']}",
        headers=auth_headers(tokens_b["access_token"]),
    )
    assert response.status_code == 404


async def test_project_isolated_between_organizations(client):
    user, tokens = await create_authenticated_user(
        client, email="proj-iso@example.com", username="projiso"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="proj-iso-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="proj-iso"
    )

    org_b = await create_organization(
        client, tokens["access_token"], name="Project Iso B", slug="project-iso-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])

    response = await client.get(
        f"/v1/projects/{project['id']}",
        headers=auth_headers(switched["access_token"]),
    )
    assert response.status_code == 404


async def test_requirement_isolated_between_organizations(client):
    user, tokens = await create_authenticated_user(
        client, email="req-iso@example.com", username="reqiso"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="req-iso-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="req-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    org_b = await create_organization(
        client, tokens["access_token"], name="Req Iso B", slug="req-iso-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])

    response = await client.get(
        f"/v1/requirements/{requirement['id']}",
        headers=auth_headers(switched["access_token"]),
    )
    assert response.status_code == 404


async def test_agent_runs_list_scoped_to_organization(client):
    user, tokens = await create_authenticated_user(
        client, email="agent-iso@example.com", username="agentiso"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="agent-iso-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="agent-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    from unittest.mock import AsyncMock, patch

    mock_output = mock_product_owner_output(project_summary="Summary", total_story_points=3)
    with patch(
        "app.workflows.engine.AgentWorkflowEngine._dispatch_agent",
        new=AsyncMock(return_value=(mock_output, 100)),
    ):
        await client.post(
            "/v1/agents/product-owner/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )

    org_b = await create_organization(
        client, tokens["access_token"], name="Agent Iso B", slug="agent-iso-b"
    )
    switched = await switch_organization(client, tokens["access_token"], org_b["id"])
    runs = await client.get("/v1/agents/runs", headers=auth_headers(switched["access_token"]))
    assert runs.status_code == 200
    assert runs.json()["total"] == 0


async def test_viewer_cannot_create_workspace(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="viewer-owner@example.com", username="viewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="viewer@example.com", username="vieweruser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Viewer Org", slug="viewer-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_login = await login_user(client, email=viewer["email"])
    viewer_tokens = await switch_organization(
        client, viewer_login["access_token"], organization["id"]
    )
    response = await client.post(
        "/v1/workspaces",
        headers=auth_headers(viewer_tokens["access_token"]),
        json={"name": "Blocked", "slug": "blocked"},
    )
    assert response.status_code == 403
