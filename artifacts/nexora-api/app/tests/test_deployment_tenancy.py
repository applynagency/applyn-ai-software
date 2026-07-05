from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_deployment,
    setup_deployment_pipeline,
    switch_organization,
)


async def test_cannot_read_deployment_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="dep-iso-a@example.com", username="depisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="dep-iso-b@example.com", username="depisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Dep Org A", slug="dep-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Dep Org B", slug="dep-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="dep-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="dep-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_deployment(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/deployment/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_deployment_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="dep-art-iso-a@example.com", username="departisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="dep-art-iso-b@example.com", username="departisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Dep Art Org A", slug="dep-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Dep Art Org B", slug="dep-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="dep-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="dep-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_deployment(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/deployment/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-list-scope@example.com", username="deplistscope"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-scope-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-scope-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    await run_deployment(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/deployment/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == requirement["id"] for item in response.json()["items"])


async def test_cannot_read_deployment_logs_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="dep-log-iso-a@example.com", username="deplogisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="dep-log-iso-b@example.com", username="deplogisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Dep Log Org A", slug="dep-log-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Dep Log Org B", slug="dep-log-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="dep-log-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="dep-log-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_deployment(client, tokens_a_org["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/deployments/{deployment_id}/logs",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_delete_deployment_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="dep-del-iso-a@example.com", username="depdelisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="dep-del-iso-b@example.com", username="depdelisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Dep Del Org A", slug="dep-del-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Dep Del Org B", slug="dep-del-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="dep-del-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="dep-del-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_deployment(client, tokens_a_org["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.delete(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404
