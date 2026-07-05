from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_uiux_designer,
    setup_uiux_pipeline,
    switch_organization,
)


async def test_cannot_read_uiux_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="uiux-iso-a@example.com", username="uiuxisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="uiux-iso-b@example.com", username="uiuxisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="UIUX Org A", slug="uiux-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="UIUX Org B", slug="uiux-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="uiux-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="uiux-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/uiux/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_uiux_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="uiux-art-iso-a@example.com", username="uiuxartisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="uiux-art-iso-b@example.com", username="uiuxartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="UIUX Art Org A", slug="uiux-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="UIUX Art Org B", slug="uiux-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="uiux-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="uiux-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/uiux/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-list-scope@example.com", username="uiuxlistscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/uiux/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
