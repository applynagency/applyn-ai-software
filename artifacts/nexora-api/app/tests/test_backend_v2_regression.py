from app.models.backend_v2 import BackendV2RunStatus
from app.tests.route_helpers import collect_route_paths


def test_backend_v2_run_status_values():
    assert BackendV2RunStatus.PENDING.value == "PENDING"
    assert BackendV2RunStatus.RUNNING.value == "RUNNING"
    assert BackendV2RunStatus.COMPLETED.value == "COMPLETED"
    assert BackendV2RunStatus.FAILED.value == "FAILED"


def test_backend_v2_models_importable():
    from app.models.backend_v2 import BackendV2Artifact, BackendV2Run

    assert BackendV2Run.__tablename__ == "backend_v2_runs"
    assert BackendV2Artifact.__tablename__ == "backend_v2_artifacts"


def test_backend_v2_service_importable():
    from app.services.backend_v2 import BackendDeveloperV2Service

    assert BackendDeveloperV2Service.__name__ == "BackendDeveloperV2Service"


def test_backend_v2_agent_importable():
    from app.agents.backend_v2 import BackendDeveloperV2Agent

    assert BackendDeveloperV2Agent.__name__ == "BackendDeveloperV2Agent"


def test_backend_v2_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/backend-v2" in path for path in paths)


def test_backend_v2_validator_importable():
    from app.backend_v2.validator import BackendDeveloperV2Validator

    assert BackendDeveloperV2Validator.__name__ == "BackendDeveloperV2Validator"


def test_backend_v2_markdown_importable():
    from app.backend_v2.markdown import output_to_markdown

    assert callable(output_to_markdown)


def test_backend_v2_prompt_builder_importable():
    from app.backend_v2.prompt_builder import BackendDeveloperV2PromptBuilder

    assert BackendDeveloperV2PromptBuilder.get_prompt_version() == "1.0.0"


def test_backend_v2_repository_importable():
    from app.repositories.backend_v2 import BackendV2ArtifactRepository, BackendV2RunRepository

    assert BackendV2RunRepository.__name__ == "BackendV2RunRepository"
    assert BackendV2ArtifactRepository.__name__ == "BackendV2ArtifactRepository"


def test_mock_backend_v2_output_satisfies_minimums():
    from app.backend_v2.validator import BackendDeveloperV2Validator
    from app.tests.conftest import mock_backend_v2_output

    result = BackendDeveloperV2Validator().validate(mock_backend_v2_output())
    assert result.is_valid is True
