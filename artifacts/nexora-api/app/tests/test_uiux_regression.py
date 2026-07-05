from app.models.uiux_designer import UIUXRunStatus
from app.tests.route_helpers import collect_route_paths


def test_uiux_run_status_values():
    assert UIUXRunStatus.PENDING.value == "PENDING"
    assert UIUXRunStatus.RUNNING.value == "RUNNING"
    assert UIUXRunStatus.COMPLETED.value == "COMPLETED"
    assert UIUXRunStatus.FAILED.value == "FAILED"


def test_uiux_models_importable():
    from app.models.uiux_designer import UIUXArtifact, UIUXRun

    assert UIUXRun.__tablename__ == "uiux_runs"
    assert UIUXArtifact.__tablename__ == "uiux_artifacts"


def test_uiux_service_importable():
    from app.services.uiux_designer import UIUXDesignerService

    assert UIUXDesignerService.__name__ == "UIUXDesignerService"


def test_uiux_agent_importable():
    from app.agents.uiux_designer import UIUXDesignerAgent

    assert UIUXDesignerAgent.__name__ == "UIUXDesignerAgent"


def test_uiux_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/uiux" in path for path in paths)
