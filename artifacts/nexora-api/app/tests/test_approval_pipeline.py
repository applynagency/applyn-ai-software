from app.approval_workflow.processor import PROCESSOR_VERSION
from app.models.approval import WorkflowApprovalStatus
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_approval_workflow_output,
    run_approval,
    setup_approval_pipeline,
)


def test_processor_version_constant():
    assert PROCESSOR_VERSION == "1.0.0"


def test_mock_output_includes_review_checklist():
    output = mock_approval_workflow_output()
    assert len(output.review_checklist) == 8


def test_mock_output_has_under_review_status():
    output = mock_approval_workflow_output()
    assert output.approval_status == WorkflowApprovalStatus.UNDER_REVIEW.value


def test_mock_output_has_deployment_readiness():
    output = mock_approval_workflow_output()
    assert output.deployment_readiness["ready_for_deployment"] is True


async def test_setup_pipeline_includes_fullstack_assembly_run(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-fsa@example.com", username="apprpipefsa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-fsa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-fsa-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    assert "fullstack_assembly_run" in pipeline
    assert pipeline["fullstack_assembly_run"]["status"] == "COMPLETED"


async def test_setup_pipeline_includes_frontend_execution_run(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-setup@example.com", username="apprpipesetup"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    assert "frontend_execution_run" in pipeline
    assert pipeline["frontend_execution_run"]["status"] == "COMPLETED"


async def test_run_links_fullstack_assembly_run(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-link@example.com", username="apprpipelink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["fullstack_assembly_run_id"] == pipeline["fullstack_assembly_run"]["id"]


async def test_run_stores_approval_status_and_validation_score(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-status@example.com", username="apprpipestatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-st-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-st-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["approval_status"] == WorkflowApprovalStatus.UNDER_REVIEW.value
    assert data["validation_score"] is not None


async def test_run_stores_processor_version_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-version@example.com", username="apprpipeversion"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["processor_version"] == PROCESSOR_VERSION
    assert created.json()["artifact"]["processor_version"] == PROCESSOR_VERSION


async def test_artifact_contains_package_sections_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-art@example.com", username="apprpipeart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-art-proj"
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


async def test_run_links_frontend_execution_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-fe@example.com", username="apprpipefe"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-fe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-fe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["frontend_execution_run_id"] == pipeline["frontend_execution_run"]["id"]


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-pipe-complete@example.com", username="apprpipecomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-pipe-cmp-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-pipe-cmp-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None
