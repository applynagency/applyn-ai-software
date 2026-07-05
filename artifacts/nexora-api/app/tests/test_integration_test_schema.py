import pytest

from app.models.integration_test import IntegrationTestRunStatus
from app.schemas.integration_test import (
    IntegrationTestArtifactResponse,
    IntegrationTestOutput,
    IntegrationTestRunRequest,
    IntegrationTestRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_integration_test_output


def test_mock_output_is_valid_schema():
    output = mock_integration_test_output()
    assert isinstance(output, IntegrationTestOutput)
    dumped = output.model_dump(mode="json")
    assert "api_test_cases" in dumped
    assert "frontend_backend_flows" in dumped
    assert "database_validation" in dumped
    assert "integration_coverage" in dumped



def test_run_request_defaults():
    request = IntegrationTestRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"


@pytest.mark.parametrize("status", list(IntegrationTestRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"sample": 1})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_integration_test_output()
    restored = IntegrationTestOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert IntegrationTestRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert IntegrationTestArtifactResponse.model_config.get("from_attributes") is True
