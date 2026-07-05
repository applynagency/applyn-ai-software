from app.models.backend_v3 import BackendV3RunStatus
from app.tests.route_helpers import collect_route_paths


def test_backend_v3_run_status_values():
    assert BackendV3RunStatus.PENDING.value == "PENDING"
    assert BackendV3RunStatus.RUNNING.value == "RUNNING"
    assert BackendV3RunStatus.COMPLETED.value == "COMPLETED"
    assert BackendV3RunStatus.FAILED.value == "FAILED"


def test_backend_v3_models_importable():
    from app.models.backend_v3 import BackendV3Artifact, BackendV3Run

    assert BackendV3Run.__tablename__ == "backend_v3_runs"
    assert BackendV3Artifact.__tablename__ == "backend_v3_artifacts"


def test_backend_v3_service_importable():
    from app.services.backend_v3 import BackendDeveloperV3Service

    assert BackendDeveloperV3Service.__name__ == "BackendDeveloperV3Service"


def test_backend_v3_agent_importable():
    from app.agents.backend_v3 import BackendDeveloperV3Agent

    assert BackendDeveloperV3Agent.__name__ == "BackendDeveloperV3Agent"


def test_backend_v3_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/backend-v3" in path for path in paths)
