from unittest.mock import AsyncMock, patch

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_business_analyst_output,
    patch_business_analyst_agent,
    run_business_analyst,
    switch_organization,
)


async def test_developer_can_run_business_analyst(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-dev-owner@example.com", username="badevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="ba-dev-user@example.com", username="badevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA Dev Org", slug="ba-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="ba-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="ba-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_business_analyst(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_business_analyst_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-view-owner@example.com", username="baviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="ba-view-dev@example.com", username="baviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA View Org", slug="ba-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="ba-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="ba-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, owner_in_org["access_token"], requirement["id"])
    created = await run_business_analyst(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get(
        f"/v1/agents/business-analyst/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_business_analyst(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-viewer-owner@example.com", username="baviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="ba-viewer@example.com", username="baviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA Viewer Org", slug="ba-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="ba-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="ba-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_business_analyst(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_business_analyst(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-pm-owner@example.com", username="bapmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="ba-pm@example.com", username="bapm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA PM Org", slug="ba-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="ba-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="ba-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, pm_tokens["access_token"], requirement["id"])
    response = await run_business_analyst(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-fail-val@example.com", username="bafailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    invalid = mock_business_analyst_output()
    invalid.functional_requirements = invalid.functional_requirements[:1]
    with patch_business_analyst_agent():
        with patch(
            "app.services.business_analyst.BusinessAnalystAgent.run",
            new=AsyncMock(return_value=(invalid, 50)),
        ):
            response = await client.post(
                "/v1/agents/business-analyst/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
