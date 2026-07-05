from unittest.mock import AsyncMock, patch

from app.schemas.kubernetes_agent import KubernetesAgentOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_kubernetes_agent_output,
    patch_kubernetes_agent,
    run_kubernetes_agents,
    setup_kubernetes_pipeline,
    switch_organization,
)


async def test_developer_can_run_kubernetes_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="k8s-dev-owner@example.com", username="k8sdvowner")
    developer, _ = await create_authenticated_user(client, email="k8s-dev@example.com", username="k8sdvdev")
    organization = await create_organization(client, owner_tokens["access_token"], name="K8s Dev Org", slug="k8s-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="k8s-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="k8s-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_kubernetes_agents(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_kubernetes_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="k8s-viewer-owner@example.com", username="k8svwowner")
    viewer, _ = await create_authenticated_user(client, email="k8s-viewer@example.com", username="k8svwview")
    organization = await create_organization(client, owner_tokens["access_token"], name="K8s View Org", slug="k8s-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="k8s-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="k8s-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_kubernetes_agents(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_kubernetes_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="k8s-pm-owner@example.com", username="k8spmowner")
    pm, _ = await create_authenticated_user(client, email="k8s-pm@example.com", username="k8spmuser")
    organization = await create_organization(client, owner_tokens["access_token"], name="K8s PM Org", slug="k8s-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="k8s-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="k8s-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_kubernetes_agents(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_unauthenticated_cannot_run_kubernetes_agent(client):
    response = await client.post("/v1/agents/kubernetes/run", json={"requirement_id": "missing"})
    assert response.status_code in (401, 403)


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="k8s-val-fail@example.com", username="k8svalfail")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_kubernetes_agent_output()
    data = invalid.model_dump(mode="json")
    data["deployments"] = []
    invalid_output = KubernetesAgentOutput(**data)
    with patch_kubernetes_agent():
        with patch("app.services.kubernetes.KubernetesAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/kubernetes/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
