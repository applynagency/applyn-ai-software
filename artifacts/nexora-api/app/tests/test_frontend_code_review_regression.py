from app.models.frontend_code_review import FrontendCodeReviewRunStatus
from app.tests.route_helpers import collect_route_paths


def test_frontend_code_review_run_status_values():
    assert FrontendCodeReviewRunStatus.PENDING.value == "PENDING"
    assert FrontendCodeReviewRunStatus.RUNNING.value == "RUNNING"
    assert FrontendCodeReviewRunStatus.COMPLETED.value == "COMPLETED"
    assert FrontendCodeReviewRunStatus.FAILED.value == "FAILED"


def test_frontend_code_review_models_importable():
    from app.models.frontend_code_review import FrontendCodeReviewArtifact, FrontendCodeReviewRun

    assert FrontendCodeReviewRun.__tablename__ == "frontend_code_review_runs"
    assert FrontendCodeReviewArtifact.__tablename__ == "frontend_code_review_artifacts"


def test_frontend_code_review_service_importable():
    from app.services.frontend_code_review import FrontendCodeReviewService

    assert FrontendCodeReviewService.__name__ == "FrontendCodeReviewService"


def test_frontend_code_review_agent_importable():
    from app.agents.frontend_code_review import FrontendCodeReviewAgent

    assert FrontendCodeReviewAgent.__name__ == "FrontendCodeReviewAgent"


def test_frontend_code_review_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/frontend-code-review" in path for path in paths)
