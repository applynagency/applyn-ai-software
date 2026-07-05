import pytest

from app.models.docker_agent import DockerAgentRunStatus
from app.schemas.docker_agent import (
    DockerAgentArtifactResponse,
    DockerAgentOutput,
    DockerAgentRunRequest,
    DockerAgentRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_docker_agent_output


def test_mock_output_is_valid_schema():
    output = mock_docker_agent_output()
    assert isinstance(output, DockerAgentOutput)
    dumped = output.model_dump(mode="json")
    assert "dockerfile_strategy" in dumped
    assert "docker_compose" in dumped
    assert "container_topology" in dumped
    assert "security_hardening" in dumped


def test_run_request_defaults():
    request = DockerAgentRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"


@pytest.mark.parametrize("status", list(DockerAgentRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"sample": 1})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_docker_agent_output()
    restored = DockerAgentOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert DockerAgentRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert DockerAgentArtifactResponse.model_config.get("from_attributes") is True
