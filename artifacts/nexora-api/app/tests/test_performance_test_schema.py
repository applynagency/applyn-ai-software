import pytest

from app.models.performance_test import PerformanceTestRunStatus
from app.schemas.performance_test import (
    PerformanceTestArtifactResponse,
    PerformanceTestOutput,
    PerformanceTestRunRequest,
    PerformanceTestRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_performance_test_output


def test_mock_output_is_valid_schema():
    output = mock_performance_test_output()
    assert isinstance(output, PerformanceTestOutput)
    dumped = output.model_dump(mode="json")
    assert "load_test_plan" in dumped
    assert "stress_test_plan" in dumped
    assert "performance_bottlenecks" in dumped
    assert "scaling_recommendations" in dumped
    assert "caching_recommendations" in dumped



def test_run_request_defaults():
    request = PerformanceTestRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"


@pytest.mark.parametrize("status", list(PerformanceTestRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"sample": 1})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_performance_test_output()
    restored = PerformanceTestOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert PerformanceTestRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert PerformanceTestArtifactResponse.model_config.get("from_attributes") is True
