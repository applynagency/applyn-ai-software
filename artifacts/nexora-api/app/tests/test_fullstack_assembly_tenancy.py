from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_fullstack_assembly,
    setup_fullstack_assembly_pipeline,
    switch_organization,
)


async def test_cannot_read_fullstack_assembly_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fsa-iso-a@example.com", username="fsaisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fsa-iso-b@example.com", username="fsaisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FSA Org A", slug="fsa-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FSA Org B", slug="fsa-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fsa-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fsa-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    created = await run_fullstack_assembly(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/fullstack-assembly/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_fullstack_assembly_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fsa-art-iso-a@example.com", username="fsaartisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fsa-art-iso-b@example.com", username="fsaartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FSA Art Org A", slug="fsa-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FSA Art Org B", slug="fsa-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fsa-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fsa-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    created = await run_fullstack_assembly(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/fullstack-assembly/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-list-scope@example.com", username="fsalistscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/fullstack-assembly/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
