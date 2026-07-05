from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_code_review,
    setup_frontend_code_review_pipeline,
    switch_organization,
)


async def test_cannot_read_frontend_code_review_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fcr-iso-a@example.com", username="fcrisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fcr-iso-b@example.com", username="fcrisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FCR Org A", slug="fcr-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FCR Org B", slug="fcr-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fcr-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fcr-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    created = await run_frontend_code_review(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/frontend-code-review/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_frontend_code_review_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="fcr-art-iso-a@example.com", username="fcrartisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="fcr-art-iso-b@example.com", username="fcrartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="FCR Art Org A", slug="fcr-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="FCR Art Org B", slug="fcr-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="fcr-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="fcr-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    created = await run_frontend_code_review(
        client, tokens_a_org["access_token"], requirement["id"]
    )
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/frontend-code-review/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-list-scope@example.com", username="fcrlistscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-code-review/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])
