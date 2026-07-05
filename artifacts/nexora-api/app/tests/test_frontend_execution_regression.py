from app.models.frontend_execution import FrontendExecutionRunStatus
from app.tests.route_helpers import collect_route_paths


def test_frontend_execution_run_status_values():
    assert FrontendExecutionRunStatus.PENDING.value == "PENDING"
    assert FrontendExecutionRunStatus.RUNNING.value == "RUNNING"
    assert FrontendExecutionRunStatus.COMPLETED.value == "COMPLETED"
    assert FrontendExecutionRunStatus.FAILED.value == "FAILED"


def test_frontend_execution_models_importable():
    from app.models.frontend_execution import FrontendExecutionArtifact, FrontendExecutionRun

    assert FrontendExecutionRun.__tablename__ == "frontend_execution_runs"
    assert FrontendExecutionArtifact.__tablename__ == "frontend_execution_artifacts"


def test_frontend_execution_service_importable():
    from app.services.frontend_execution import FrontendExecutionService

    assert FrontendExecutionService.__name__ == "FrontendExecutionService"


def test_frontend_execution_agent_importable():
    from app.agents.frontend_execution import FrontendExecutionAgent

    assert FrontendExecutionAgent.__name__ == "FrontendExecutionAgent"


def test_frontend_execution_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/frontend-execution" in path for path in paths)
