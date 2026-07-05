from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_v3,
    setup_backend_v3_pipeline,
    switch_organization,
)


async def test_cannot_read_backend_v3_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fv3-iso-a@example.com", username="fv3isoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fv3-iso-b@example.com", username="fv3isob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FV3 Org A", slug="fv3-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FV3 Org B", slug="fv3-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fv3-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fv3-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_backend_v3_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_backend_v3(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-v3/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_backend_v3_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fv3-art-iso-a@example.com", username="fv3artisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fv3-art-iso-b@example.com", username="fv3artisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FV3 Art Org A", slug="fv3-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FV3 Art Org B", slug="fv3-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fv3-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fv3-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_backend_v3_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_backend_v3(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-v3/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-list-scope@example.com", username="fv3listscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_v3(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-v3/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
