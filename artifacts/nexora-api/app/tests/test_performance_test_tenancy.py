from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_performance_tests,
    setup_performance_test_pipeline,
    switch_organization,
)


async def test_cannot_read_performance_test_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="performance_test-iso-a@example.com", username="performaisoa")
    _, tokens_b = await create_authenticated_user(client, email="performance_test-iso-b@example.com", username="performaisob")
    org_a = await create_organization(client, tokens_a["access_token"], name="PerformanceTest Org A", slug="performance_test-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="PerformanceTest Org B", slug="performance_test-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="performance_test-iso-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="performance_test-iso-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_performance_tests(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/performance-tests/runs/{run_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404


async def test_cannot_read_performance_test_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="performance_test-art-a@example.com", username="performaarta")
    _, tokens_b = await create_authenticated_user(client, email="performance_test-art-b@example.com", username="performaartb")
    org_a = await create_organization(client, tokens_a["access_token"], name="PerformanceTest Art Org A", slug="performance_test-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="PerformanceTest Art Org B", slug="performance_test-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="performance_test-art-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="performance_test-art-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_performance_tests(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/performance-tests/artifacts/{artifact_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404
