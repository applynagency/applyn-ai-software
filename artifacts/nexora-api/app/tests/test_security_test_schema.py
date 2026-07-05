import pytest

from app.models.security_test import SecurityTestRunStatus
from app.schemas.security_test import (
    SecurityTestArtifactResponse,
    SecurityTestOutput,
    SecurityTestRunRequest,
    SecurityTestRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_security_test_output


def test_mock_output_is_valid_schema():
    output = mock_security_test_output()
    assert isinstance(output, SecurityTestOutput)
    dumped = output.model_dump(mode="json")
    assert "owasp_assessment" in dumped
    assert "authentication_review" in dumped
    assert "authorization_review" in dumped
    assert "input_validation_review" in dumped
    assert "dependency_security_scan" in dumped
    assert "secrets_exposure_review" in dumped



def test_run_request_defaults():
    request = SecurityTestRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"


@pytest.mark.parametrize("status", list(SecurityTestRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"sample": 1})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_security_test_output()
    restored = SecurityTestOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert SecurityTestRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert SecurityTestArtifactResponse.model_config.get("from_attributes") is True
