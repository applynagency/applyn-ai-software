from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_execution,
    setup_backend_execution_pipeline,
    switch_organization,
)


async def test_cannot_read_backend_execution_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fe-iso-a@example.com", username="feisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fe-iso-b@example.com", username="feisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FE Org A", slug="fe-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FE Org B", slug="fe-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fe-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fe-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    created = await run_backend_execution(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-execution/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_backend_execution_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fe-art-iso-a@example.com", username="feartisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fe-art-iso-b@example.com", username="feartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FE Art Org A", slug="fe-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FE Art Org B", slug="fe-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fe-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fe-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    created = await run_backend_execution(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-execution/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-list-scope@example.com", username="felistscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_execution(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-execution/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
