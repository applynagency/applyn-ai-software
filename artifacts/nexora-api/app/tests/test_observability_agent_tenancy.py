from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_observability_agents,
    setup_observability_pipeline,
    switch_organization,
)


async def test_cannot_read_observability_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="obs-iso-a@example.com", username="obsisoa")
    _, tokens_b = await create_authenticated_user(client, email="obs-iso-b@example.com", username="obsisob")
    org_a = await create_organization(client, tokens_a["access_token"], name="Obs Org A", slug="obs-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="Obs Org B", slug="obs-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="obs-iso-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="obs-iso-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_observability_agents(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/observability/runs/{run_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404


async def test_cannot_read_observability_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="obs-art-a@example.com", username="obsarta")
    _, tokens_b = await create_authenticated_user(client, email="obs-art-b@example.com", username="obsartb")
    org_a = await create_organization(client, tokens_a["access_token"], name="Obs Art Org A", slug="obs-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="Obs Art Org B", slug="obs-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="obs-art-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="obs-art-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_observability_agents(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/observability/artifacts/{artifact_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404
