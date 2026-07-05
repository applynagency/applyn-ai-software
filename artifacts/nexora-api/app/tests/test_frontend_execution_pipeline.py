from app.frontend_execution import EXECUTION_STEPS, EXECUTOR_VERSION
from app.frontend_execution.executor import FrontendExecutionExecutor
from app.models.frontend_execution import FrontendExecutionApprovalStatus
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_frontend_execution_output,
    run_frontend_execution,
    setup_frontend_execution_pipeline,
)


def test_execution_steps_has_five_pipeline_commands():
    assert len(EXECUTION_STEPS) == 5


def test_execution_steps_starts_with_install():
    assert EXECUTION_STEPS[0] == ("npm install", "install")


def test_execution_steps_build_before_test():
    step_names = [step_name for _, step_name in EXECUTION_STEPS]
    assert step_names.index("build") < step_names.index("test")


def test_execution_steps_includes_lint_and_typecheck():
    step_names = {step_name for _, step_name in EXECUTION_STEPS}
    assert step_names == {"install", "lint", "typecheck", "build", "test"}


def test_executor_version_constant():
    assert EXECUTOR_VERSION == "1.0.0"
    assert FrontendExecutionExecutor.get_executor_version() == EXECUTOR_VERSION


def test_mock_output_includes_all_step_results():
    output = mock_frontend_execution_output()
    assert output.install_results["command"] == "npm install"
    assert output.lint_results["command"] == "npm run lint"
    assert output.typecheck_results["command"] == "npm run type-check"
    assert output.build_results["command"] == "npm run build"
    assert output.test_results["command"] == "npm test"


def test_mock_output_logs_reference_each_step():
    output = mock_frontend_execution_output()
    joined = "\n".join(output.execution_logs)
    assert "npm install" in joined
    assert "npm run lint" in joined
    assert "npm run type-check" in joined
    assert "npm run build" in joined
    assert "npm test" in joined


async def test_setup_pipeline_includes_code_review_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-pipe-setup@example.com", username="fepipesetup"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-pipe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-pipe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_frontend_execution_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    assert "frontend_v3_run" in pipeline
    assert "frontend_code_review_run" in pipeline
    assert pipeline["frontend_code_review_run"]["status"] == "COMPLETED"


async def test_run_links_v3_and_code_review_runs(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-pipe-link@example.com", username="fepipelink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-pipe-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-pipe-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_frontend_execution_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    created = await run_frontend_execution(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["frontend_v3_run_id"] == pipeline["frontend_v3_run"]["id"]
    assert data["frontend_code_review_run_id"] == pipeline["frontend_code_review_run"]["id"]


async def test_run_stores_build_validation_and_approval_status(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-pipe-status@example.com", username="fepipestatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-pipe-st-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-pipe-st-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_execution(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["build_status"] == "success"
    assert data["validation_status"] == "passed"
    assert data["approval_status"] == FrontendExecutionApprovalStatus.FRONTEND_APPROVED.value


async def test_run_stores_executor_version_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-pipe-version@example.com", username="fepipeversion"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-pipe-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-pipe-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_execution(client, tokens["access_token"], requirement["id"])
    assert created.json()["executor_version"] == EXECUTOR_VERSION
    assert created.json()["artifact"]["executor_version"] == EXECUTOR_VERSION


async def test_artifact_contains_execution_logs_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-pipe-logs@example.com", username="fepipelogs"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-pipe-log-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-pipe-log-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_execution(client, tokens["access_token"], requirement["id"])
    logs = created.json()["artifact"]["artifact_json"]["execution_logs"]
    assert len(logs) >= len(EXECUTION_STEPS)
