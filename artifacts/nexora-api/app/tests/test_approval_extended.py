from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_approval,
    setup_approval_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-schema@example.com", username="apprschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "approval_summary",
        "review_checklist",
        "deployment_readiness",
        "recommendation",
        "approval_status",
    ):
        assert key in artifact


async def test_run_stores_processor_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-meta@example.com", username="apprmeta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["processor_version"] is not None
    assert data["artifact"]["processor_version"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-history@example.com", username="apprhistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    await run_approval(client, tokens["access_token"], requirement["id"])
    await run_approval(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/approval/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-complete@example.com", username="apprcomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_checklist_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-checklist@example.com", username="apprchecklist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-chk-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-chk-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    checklist = created.json()["artifact"]["artifact_json"]["review_checklist"]
    assert len(checklist) == 8


async def test_deployment_readiness_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-ready@example.com", username="apprready"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-ready-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-ready-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    readiness = created.json()["artifact"]["artifact_json"]["deployment_readiness"]
    assert readiness["ready_for_deployment"] is True
    assert readiness["readiness_score"] == 100.0


async def test_approval_summary_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-summary@example.com", username="apprsummary"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-sum-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-sum-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    summary = created.json()["artifact"]["artifact_json"]["approval_summary"]
    assert summary["review_summary"]["assembly_status"] == "ASSEMBLY_APPROVED"


async def test_under_review_status_stored_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-under-review@example.com", username="apprunderreview"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-ur-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-ur-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["approval_status"] == "UNDER_REVIEW"


async def test_validation_score_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-score@example.com", username="apprscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-score-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-score-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["validation_score"] >= 80


async def test_recommendation_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-rec-art@example.com", username="apprrecart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-rec-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-rec-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    recommendation = created.json()["artifact"]["artifact_json"]["recommendation"]
    assert recommendation in ("APPROVE", "REVIEW", "REJECT")
