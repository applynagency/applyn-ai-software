from app.models.backend_v1 import BackendV1RunStatus
from app.tests.route_helpers import collect_route_paths


def test_backend_v1_run_status_values():
    assert BackendV1RunStatus.PENDING.value == "PENDING"
    assert BackendV1RunStatus.RUNNING.value == "RUNNING"
    assert BackendV1RunStatus.COMPLETED.value == "COMPLETED"
    assert BackendV1RunStatus.FAILED.value == "FAILED"


def test_backend_v1_models_importable():
    from app.models.backend_v1 import BackendV1Artifact, BackendV1Run

    assert BackendV1Run.__tablename__ == "backend_v1_runs"
    assert BackendV1Artifact.__tablename__ == "backend_v1_artifacts"


def test_backend_v1_service_importable():
    from app.services.backend_v1 import BackendDeveloperV1Service

    assert BackendDeveloperV1Service.__name__ == "BackendDeveloperV1Service"


def test_backend_v1_agent_importable():
    from app.agents.backend_v1 import BackendDeveloperV1Agent

    assert BackendDeveloperV1Agent.__name__ == "BackendDeveloperV1Agent"


def test_backend_v1_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/backend-v1" in path for path in paths)


def test_backend_v1_validator_importable():
    from app.backend_v1.validator import BackendDeveloperV1Validator

    assert BackendDeveloperV1Validator.__name__ == "BackendDeveloperV1Validator"


def test_backend_v1_markdown_importable():
    from app.backend_v1.markdown import output_to_markdown

    assert callable(output_to_markdown)


def test_backend_v1_prompt_builder_importable():
    from app.backend_v1.prompt_builder import BackendDeveloperV1PromptBuilder

    assert BackendDeveloperV1PromptBuilder.get_prompt_version() == "1.0.0"


def test_backend_v1_repository_importable():
    from app.repositories.backend_v1 import BackendV1ArtifactRepository, BackendV1RunRepository

    assert BackendV1RunRepository.__name__ == "BackendV1RunRepository"
    assert BackendV1ArtifactRepository.__name__ == "BackendV1ArtifactRepository"


def test_mock_backend_v1_output_satisfies_minimums():
    from app.backend_v1.validator import BackendDeveloperV1Validator
    from app.tests.conftest import mock_backend_v1_output

    result = BackendDeveloperV1Validator().validate(mock_backend_v1_output())
    assert result.is_valid is True
