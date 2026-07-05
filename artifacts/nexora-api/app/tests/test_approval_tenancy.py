from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_approval,
    setup_approval_pipeline,
    switch_organization,
)


async def test_cannot_read_approval_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="appr-iso-a@example.com", username="apprisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="appr-iso-b@example.com", username="apprisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Appr Org A", slug="appr-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Appr Org B", slug="appr-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="appr-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="appr-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_approval(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/approval/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_approval_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="appr-art-iso-a@example.com", username="apprartisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="appr-art-iso-b@example.com", username="apprartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Appr Art Org A", slug="appr-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Appr Art Org B", slug="appr-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="appr-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="appr-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_approval(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/approval/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-list-scope@example.com", username="apprlistscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    await run_approval(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/approval/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
