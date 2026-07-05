from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_sre_approvals,
    setup_sre_approval_pipeline,
    switch_organization,
)


async def test_cannot_read_sre_approval_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="sre-iso-a@example.com", username="sreisoa")
    _, tokens_b = await create_authenticated_user(client, email="sre-iso-b@example.com", username="sreisob")
    org_a = await create_organization(client, tokens_a["access_token"], name="Sre Org A", slug="sre-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="Sre Org B", slug="sre-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="sre-iso-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="sre-iso-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_sre_approvals(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/sre-approval/runs/{run_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404


async def test_cannot_read_sre_approval_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="sre-art-a@example.com", username="srearta")
    _, tokens_b = await create_authenticated_user(client, email="sre-art-b@example.com", username="sreartb")
    org_a = await create_organization(client, tokens_a["access_token"], name="Sre Art Org A", slug="sre-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="Sre Art Org B", slug="sre-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="sre-art-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="sre-art-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_sre_approvals(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/sre-approval/artifacts/{artifact_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404
