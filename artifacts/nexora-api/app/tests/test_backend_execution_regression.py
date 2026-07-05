from app.models.backend_execution import BackendExecutionRunStatus
from app.tests.route_helpers import collect_route_paths


def test_backend_execution_run_status_values():
    assert BackendExecutionRunStatus.PENDING.value == "PENDING"
    assert BackendExecutionRunStatus.RUNNING.value == "RUNNING"
    assert BackendExecutionRunStatus.COMPLETED.value == "COMPLETED"
    assert BackendExecutionRunStatus.FAILED.value == "FAILED"


def test_backend_execution_models_importable():
    from app.models.backend_execution import BackendExecutionArtifact, BackendExecutionRun

    assert BackendExecutionRun.__tablename__ == "backend_execution_runs"
    assert BackendExecutionArtifact.__tablename__ == "backend_execution_artifacts"


def test_backend_execution_service_importable():
    from app.services.backend_execution import BackendExecutionService

    assert BackendExecutionService.__name__ == "BackendExecutionService"


def test_backend_execution_agent_importable():
    from app.agents.backend_execution import BackendExecutionAgent

    assert BackendExecutionAgent.__name__ == "BackendExecutionAgent"


def test_backend_execution_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/backend-execution" in path for path in paths)
