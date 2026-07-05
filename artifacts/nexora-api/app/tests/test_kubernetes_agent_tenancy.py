from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_kubernetes_agents,
    setup_kubernetes_pipeline,
    switch_organization,
)


async def test_cannot_read_kubernetes_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="k8s-iso-a@example.com", username="k8sisoa")
    _, tokens_b = await create_authenticated_user(client, email="k8s-iso-b@example.com", username="k8sisob")
    org_a = await create_organization(client, tokens_a["access_token"], name="K8s Org A", slug="k8s-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="K8s Org B", slug="k8s-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="k8s-iso-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="k8s-iso-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_kubernetes_agents(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/kubernetes/runs/{run_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404


async def test_cannot_read_kubernetes_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="k8s-art-a@example.com", username="k8sarta")
    _, tokens_b = await create_authenticated_user(client, email="k8s-art-b@example.com", username="k8sartb")
    org_a = await create_organization(client, tokens_a["access_token"], name="K8s Art Org A", slug="k8s-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="K8s Art Org B", slug="k8s-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="k8s-art-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="k8s-art-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_kubernetes_agents(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/kubernetes/artifacts/{artifact_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404
