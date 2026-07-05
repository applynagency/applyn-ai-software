from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_architect,
    setup_qa_architect_pipeline,
    switch_organization,
)


async def test_cannot_read_qa_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(
        client, email="qa-iso-a@example.com", username="qaisoa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="qa-iso-b@example.com", username="qaisob"
    )
    org_a = await create_organization(client, tokens_a["access_token"], name="QA Org A", slug="qa-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="QA Org B", slug="qa-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="qa-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="qa-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/qa-architect/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_qa_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(
        client, email="qa-art-iso-a@example.com", username="qaartisoa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="qa-art-iso-b@example.com", username="qaartisob"
    )
    org_a = await create_organization(client, tokens_a["access_token"], name="QA Art Org A", slug="qa-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="QA Art Org B", slug="qa-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="qa-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="qa-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/qa-architect/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404
