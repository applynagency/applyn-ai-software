from app.models.frontend_v3 import FrontendV3RunStatus
from app.tests.route_helpers import collect_route_paths


def test_frontend_v3_run_status_values():
    assert FrontendV3RunStatus.PENDING.value == "PENDING"
    assert FrontendV3RunStatus.RUNNING.value == "RUNNING"
    assert FrontendV3RunStatus.COMPLETED.value == "COMPLETED"
    assert FrontendV3RunStatus.FAILED.value == "FAILED"


def test_frontend_v3_models_importable():
    from app.models.frontend_v3 import FrontendV3Artifact, FrontendV3Run

    assert FrontendV3Run.__tablename__ == "frontend_v3_runs"
    assert FrontendV3Artifact.__tablename__ == "frontend_v3_artifacts"


def test_frontend_v3_service_importable():
    from app.services.frontend_v3 import FrontendDeveloperV3Service

    assert FrontendDeveloperV3Service.__name__ == "FrontendDeveloperV3Service"


def test_frontend_v3_agent_importable():
    from app.agents.frontend_v3 import FrontendDeveloperV3Agent

    assert FrontendDeveloperV3Agent.__name__ == "FrontendDeveloperV3Agent"


def test_frontend_v3_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/frontend-v3" in path for path in paths)
