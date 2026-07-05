from unittest.mock import AsyncMock, patch

from app.schemas.fullstack_assembly import FullstackAssemblyOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    patch_fullstack_assembly_agent,
    run_fullstack_assembly,
    setup_fullstack_assembly_pipeline,
    switch_organization,
)


async def test_developer_can_run_fullstack_assembly(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fsa-dev-owner@example.com", username="fsadevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fsa-dev-user@example.com", username="fsadevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FSA Dev Org", slug="fsa-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fsa-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fsa-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
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
    response = await run_fullstack_assembly(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_fullstack_assembly_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fsa-view-owner@example.com", username="fsaviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fsa-view-dev@example.com", username="fsaviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FSA View Org", slug="fsa-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fsa-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fsa-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
    )
    created = await run_fullstack_assembly(
        client, owner_in_org["access_token"], requirement["id"]
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
    response = await client.get(
        f"/v1/agents/fullstack-assembly/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_fullstack_assembly(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fsa-viewer-owner@example.com", username="fsaviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="fsa-viewer@example.com", username="fsaviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FSA Viewer Org", slug="fsa-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fsa-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fsa-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_fullstack_assembly(
        client, viewer_tokens["access_token"], requirement["id"]
    )
    assert response.status_code == 403


async def test_project_manager_can_run_fullstack_assembly(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fsa-pm-owner@example.com", username="fsapmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="fsa-pm@example.com", username="fsapm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FSA PM Org", slug="fsa-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="fsa-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_fullstack_assembly(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_returns_422_without_persisted_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-fail-val@example.com", username="fsafailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = FullstackAssemblyOutput.model_construct(
        application_manifest={},
        frontend_package={},
        backend_package={"included": False},
        deployment_assets={},
        environment_variables=[],
        docker_assets={},
        infrastructure_templates={},
        health_checks={},
        startup_configuration={},
        release_metadata={},
        readme="",
        assembly_status="ASSEMBLY_APPROVED",
        package_metadata={},
    )
    with patch_fullstack_assembly_agent():
        with patch(
            "app.services.fullstack_assembly.FullStackAssemblyAgent.run",
            new=AsyncMock(return_value=invalid_output),
        ):
            response = await client.post(
                "/v1/agents/fullstack-assembly/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    list_response = await client.get(
        f"/v1/agents/fullstack-assembly/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert list_response.json()["total"] == 0
