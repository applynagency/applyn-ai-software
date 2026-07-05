from app.models.frontend_architect import FrontendArchitectRunStatus
from app.tests.route_helpers import collect_route_paths


def test_frontend_architect_run_status_values():
    assert FrontendArchitectRunStatus.PENDING.value == "PENDING"
    assert FrontendArchitectRunStatus.RUNNING.value == "RUNNING"
    assert FrontendArchitectRunStatus.COMPLETED.value == "COMPLETED"
    assert FrontendArchitectRunStatus.FAILED.value == "FAILED"


def test_frontend_architect_models_importable():
    from app.models.frontend_architect import FrontendArchitectArtifact, FrontendArchitectRun

    assert FrontendArchitectRun.__tablename__ == "frontend_architect_runs"
    assert FrontendArchitectArtifact.__tablename__ == "frontend_architect_artifacts"


def test_frontend_architect_service_importable():
    from app.services.frontend_architect import FrontendArchitectService

    assert FrontendArchitectService.__name__ == "FrontendArchitectService"


def test_frontend_architect_agent_importable():
    from app.agents.frontend_architect import FrontendArchitectAgent

    assert FrontendArchitectAgent.__name__ == "FrontendArchitectAgent"


def test_frontend_architect_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/frontend-architect" in path for path in paths)
