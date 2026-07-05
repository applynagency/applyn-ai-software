from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_v2,
    setup_backend_v2_pipeline,
    switch_organization,
)


async def test_cannot_read_backend_v2_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="bv2-iso-a@example.com", username="bv2isoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="bv2-iso-b@example.com", username="bv2isob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="BV2 Org A", slug="bv2-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="BV2 Org B", slug="bv2-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="bv2-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="bv2-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-v2/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_backend_v2_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="bv2-art-iso-a@example.com", username="bv2artisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="bv2-art-iso-b@example.com", username="bv2artisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="BV2 Art Org A", slug="bv2-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="BV2 Art Org B", slug="bv2-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="bv2-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="bv2-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-v2/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-list-scope@example.com", username="bv2listscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_v2(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-v2/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
