from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_security_tests,
    setup_security_test_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="security_test-schema@example.com", username="securitysch")
    workspace = await create_workspace(client, tokens["access_token"], slug="security_test-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="security_test-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_security_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_security_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert "owasp_assessment" in artifact
    assert "authentication_review" in artifact
    assert "authorization_review" in artifact
    assert "input_validation_review" in artifact
    assert "dependency_security_scan" in artifact
    assert "secrets_exposure_review" in artifact



async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="security_test-meta@example.com", username="securitymet")
    workspace = await create_workspace(client, tokens["access_token"], slug="security_test-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="security_test-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_security_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_security_tests(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="security_test-history@example.com", username="securityhst")
    workspace = await create_workspace(client, tokens["access_token"], slug="security_test-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="security_test-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_security_test_pipeline(client, tokens["access_token"], requirement["id"])
    await run_security_tests(client, tokens["access_token"], requirement["id"])
    await run_security_tests(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/security-tests/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_required_counts_meet_minimums(client):
    _, tokens = await create_authenticated_user(client, email="security_test-mins@example.com", username="securitymin")
    workspace = await create_workspace(client, tokens["access_token"], slug="security_test-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="security_test-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_security_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_security_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["owasp_assessment"]) >= 5
    assert len(artifact["authentication_review"]) >= 3
    assert len(artifact["authorization_review"]) >= 3
    assert len(artifact["input_validation_review"]) >= 3
    assert len(artifact["dependency_security_scan"]) >= 3
    assert len(artifact["secrets_exposure_review"]) >= 3
