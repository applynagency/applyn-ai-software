from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_architect,
    setup_frontend_architect_pipeline,
    switch_organization,
)


async def test_cannot_read_frontend_architect_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fa-iso-a@example.com", username="faisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fa-iso-b@example.com", username="faisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FA Org A", slug="fa-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FA Org B", slug="fa-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fa-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fa-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/frontend-architect/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_frontend_architect_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fa-art-iso-a@example.com", username="faartisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fa-art-iso-b@example.com", username="faartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FA Art Org A", slug="fa-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FA Art Org B", slug="fa-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fa-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fa-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/frontend-architect/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-list-scope@example.com", username="falistscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-architect/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
