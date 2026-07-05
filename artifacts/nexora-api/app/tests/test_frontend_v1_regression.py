from app.models.frontend_v1 import FrontendV1RunStatus
from app.tests.route_helpers import collect_route_paths


def test_frontend_v1_run_status_values():
    assert FrontendV1RunStatus.PENDING.value == "PENDING"
    assert FrontendV1RunStatus.RUNNING.value == "RUNNING"
    assert FrontendV1RunStatus.COMPLETED.value == "COMPLETED"
    assert FrontendV1RunStatus.FAILED.value == "FAILED"


def test_frontend_v1_models_importable():
    from app.models.frontend_v1 import FrontendV1Artifact, FrontendV1Run

    assert FrontendV1Run.__tablename__ == "frontend_v1_runs"
    assert FrontendV1Artifact.__tablename__ == "frontend_v1_artifacts"


def test_frontend_v1_service_importable():
    from app.services.frontend_v1 import FrontendDeveloperV1Service

    assert FrontendDeveloperV1Service.__name__ == "FrontendDeveloperV1Service"


def test_frontend_v1_agent_importable():
    from app.agents.frontend_v1 import FrontendDeveloperV1Agent

    assert FrontendDeveloperV1Agent.__name__ == "FrontendDeveloperV1Agent"


def test_frontend_v1_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/frontend-v1" in path for path in paths)
