from app.backend_execution import EXECUTION_STEPS, EXECUTOR_VERSION
from app.backend_execution.executor import BackendExecutionExecutor
from app.models.backend_execution import BackendExecutionApprovalStatus
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_backend_execution_output,
    run_backend_execution,
    setup_backend_execution_pipeline,
)


def test_execution_steps_has_pipeline_commands():
    assert len(EXECUTION_STEPS) >= 10


def test_execution_steps_starts_with_venv():
    assert EXECUTION_STEPS[0][1] == "venv"


def test_execution_steps_includes_pip_install():
    step_names = [step_name for _, step_name in EXECUTION_STEPS]
    assert "pip_install" in step_names


def test_execution_steps_includes_ruff_mypy_pytest():
    step_names = {step_name for _, step_name in EXECUTION_STEPS}
    assert {"ruff", "mypy", "pytest", "startup"}.issubset(step_names)


def test_executor_version_constant():
    assert EXECUTOR_VERSION == "1.0.0"
    assert BackendExecutionExecutor.get_executor_version() == EXECUTOR_VERSION


def test_mock_output_includes_all_step_results():
    output = mock_backend_execution_output()
    assert output.ruff_results["command"] == "ruff check ."
    assert output.mypy_results["command"] == "mypy app"
    assert output.pytest_results["command"] == "pytest -q"
    assert output.startup_results["command"] == "import app.main"
    assert output.dependency_results["command"] == "pip check"


def test_mock_output_logs_reference_each_step():
    output = mock_backend_execution_output()
    joined = "\n".join(output.execution_logs)
    assert "pip install" in joined
    assert "ruff" in joined
    assert "mypy" in joined
    assert "pytest" in joined
    assert "startup" in joined


async def test_setup_pipeline_includes_code_review_run(client):
    _, tokens = await create_authenticated_user(
        client, email="be-pipe-setup@example.com", username="bepipesetup"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="be-pipe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="be-pipe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_backend_execution_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    assert "backend_v3_run" in pipeline
    assert "backend_code_review_run" in pipeline
    assert pipeline["backend_code_review_run"]["status"] == "COMPLETED"


async def test_run_links_v3_and_code_review_runs(client):
    _, tokens = await create_authenticated_user(
        client, email="be-pipe-link@example.com", username="bepipelink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="be-pipe-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="be-pipe-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_backend_execution_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["backend_v3_run_id"] == pipeline["backend_v3_run"]["id"]
    assert data["backend_code_review_run_id"] == pipeline["backend_code_review_run"]["id"]


async def test_run_stores_build_validation_and_approval_status(client):
    _, tokens = await create_authenticated_user(
        client, email="be-pipe-status@example.com", username="bepipestatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="be-pipe-st-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="be-pipe-st-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["build_status"] == "success"
    assert data["validation_status"] == "passed"
    assert data["approval_status"] == BackendExecutionApprovalStatus.BACKEND_APPROVED.value


async def test_run_stores_executor_version_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="be-pipe-version@example.com", username="bepipeversion"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="be-pipe-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="be-pipe-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert created.json()["executor_version"] == EXECUTOR_VERSION
    assert created.json()["artifact"]["executor_version"] == EXECUTOR_VERSION


async def test_artifact_contains_execution_logs_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="be-pipe-logs@example.com", username="bepipelogs"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="be-pipe-log-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="be-pipe-log-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    logs = created.json()["artifact"]["artifact_json"]["execution_logs"]
    assert len(logs) >= 5
