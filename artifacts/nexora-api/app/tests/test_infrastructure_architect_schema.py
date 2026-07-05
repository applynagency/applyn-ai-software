import pytest

from app.models.infrastructure_architect import InfrastructureArchitectRunStatus
from app.schemas.infrastructure_architect import (
    InfrastructureArchitectArtifactResponse,
    InfrastructureArchitectOutput,
    InfrastructureArchitectRunRequest,
    InfrastructureArchitectRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_infrastructure_architect_output


def test_mock_output_is_valid_schema():
    output = mock_infrastructure_architect_output()
    assert isinstance(output, InfrastructureArchitectOutput)
    dumped = output.model_dump(mode="json")
    assert "environments" in dumped
    assert "scaling_rules" in dumped
    assert "security_controls" in dumped
    assert "backup_recovery_plans" in dumped



def test_run_request_defaults():
    request = InfrastructureArchitectRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"


@pytest.mark.parametrize("status", list(InfrastructureArchitectRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"sample": 1})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_infrastructure_architect_output()
    restored = InfrastructureArchitectOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert InfrastructureArchitectRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert InfrastructureArchitectArtifactResponse.model_config.get("from_attributes") is True
