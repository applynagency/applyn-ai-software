from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_infrastructure_architects,
    setup_infrastructure_architect_pipeline,
    switch_organization,
)


async def test_cannot_read_infrastructure_architect_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="infrastructure_architect-iso-a@example.com", username="integratisoa")
    _, tokens_b = await create_authenticated_user(client, email="infrastructure_architect-iso-b@example.com", username="integratisob")
    org_a = await create_organization(client, tokens_a["access_token"], name="InfrastructureArchitect Org A", slug="infrastructure_architect-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="InfrastructureArchitect Org B", slug="infrastructure_architect-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="infrastructure_architect-iso-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-iso-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_infrastructure_architects(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/infrastructure-architect/runs/{run_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404


async def test_cannot_read_infrastructure_architect_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="infrastructure_architect-art-a@example.com", username="integratarta")
    _, tokens_b = await create_authenticated_user(client, email="infrastructure_architect-art-b@example.com", username="integratartb")
    org_a = await create_organization(client, tokens_a["access_token"], name="InfrastructureArchitect Art Org A", slug="infrastructure_architect-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="InfrastructureArchitect Art Org B", slug="infrastructure_architect-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="infrastructure_architect-art-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-art-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_infrastructure_architects(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/infrastructure-architect/artifacts/{artifact_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404
