from app.models.frontend_v2 import FrontendV2RunStatus
from app.tests.route_helpers import collect_route_paths


def test_frontend_v2_run_status_values():
    assert FrontendV2RunStatus.PENDING.value == "PENDING"
    assert FrontendV2RunStatus.RUNNING.value == "RUNNING"
    assert FrontendV2RunStatus.COMPLETED.value == "COMPLETED"
    assert FrontendV2RunStatus.FAILED.value == "FAILED"


def test_frontend_v2_models_importable():
    from app.models.frontend_v2 import FrontendV2Artifact, FrontendV2Run

    assert FrontendV2Run.__tablename__ == "frontend_v2_runs"
    assert FrontendV2Artifact.__tablename__ == "frontend_v2_artifacts"


def test_frontend_v2_service_importable():
    from app.services.frontend_v2 import FrontendDeveloperV2Service

    assert FrontendDeveloperV2Service.__name__ == "FrontendDeveloperV2Service"


def test_frontend_v2_agent_importable():
    from app.agents.frontend_v2 import FrontendDeveloperV2Agent

    assert FrontendDeveloperV2Agent.__name__ == "FrontendDeveloperV2Agent"


def test_frontend_v2_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/frontend-v2" in path for path in paths)
