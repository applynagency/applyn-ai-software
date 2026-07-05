import pytest

from app.models.cicd_agent import CicdRunStatus
from app.schemas.cicd_agent import (
    CicdAgentOutput,
    CicdArtifactResponse,
    CicdRunRequest,
    CicdRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_cicd_agent_output


def test_mock_output_is_valid_schema():
    output = mock_cicd_agent_output()
    assert isinstance(output, CicdAgentOutput)
    dumped = output.model_dump(mode="json")
    assert "github_actions" in dumped
    assert "azure_devops" in dumped
    assert "gitlab_ci" in dumped
    assert "rollback_strategy" in dumped


def test_run_request_defaults():
    request = CicdRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"


@pytest.mark.parametrize("status", list(CicdRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"sample": 1})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_cicd_agent_output()
    restored = CicdAgentOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert CicdRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert CicdArtifactResponse.model_config.get("from_attributes") is True
