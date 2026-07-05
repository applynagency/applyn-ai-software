from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_architect,
    run_unit_tests,
    setup_qa_architect_pipeline,
    switch_organization,
)


async def test_cannot_read_unit_test_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(
        client, email="ut-iso-a@example.com", username="utisoa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="ut-iso-b@example.com", username="utisob"
    )
    org_a = await create_organization(client, tokens_a["access_token"], name="UT Org A", slug="ut-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="UT Org B", slug="ut-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="ut-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="ut-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    await run_qa_architect(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/unit-tests/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_unit_test_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(
        client, email="ut-art-iso-a@example.com", username="utartisoa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="ut-art-iso-b@example.com", username="utartisob"
    )
    org_a = await create_organization(client, tokens_a["access_token"], name="UT Art Org A", slug="ut-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="UT Art Org B", slug="ut-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="ut-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="ut-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    await run_qa_architect(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/unit-tests/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404
