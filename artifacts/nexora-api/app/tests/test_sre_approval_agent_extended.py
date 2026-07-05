from app.models.sre_approval import SreStatus
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_sre_approval_agent,
    run_sre_approvals,
    setup_sre_approval_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="sre-schema@example.com", username="sreschema")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_sre_approvals(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for field in ("sre_status", "production_readiness_score", "findings", "recommendation"):
        assert field in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="sre-meta@example.com", username="sremeta")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_sre_approvals(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None


async def test_rejected_run_still_completes(client):
    _, tokens = await create_authenticated_user(client, email="sre-reject@example.com", username="srereject")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-rej-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-rej-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    with patch_sre_approval_agent(sre_status=SreStatus.SRE_REJECTED):
        response = await client.post(
            "/v1/agents/sre-approval/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["artifact"]["artifact_json"]["sre_status"] == "SRE_REJECTED"


async def test_approved_with_warnings_completes(client):
    _, tokens = await create_authenticated_user(client, email="sre-warn@example.com", username="srewarn")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-warn-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-warn-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    with patch_sre_approval_agent(sre_status=SreStatus.SRE_APPROVED_WITH_WARNINGS):
        response = await client.post(
            "/v1/agents/sre-approval/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )
    assert response.status_code == 201
    assert response.json()["artifact"]["artifact_json"]["sre_status"] == "SRE_APPROVED_WITH_WARNINGS"
