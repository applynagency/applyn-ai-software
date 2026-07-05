import pytest

from app.models.observability_agent import ObservabilityRunStatus
from app.schemas.observability_agent import (
    ObservabilityAgentOutput,
    ObservabilityArtifactResponse,
    ObservabilityRunRequest,
    ObservabilityRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_observability_agent_output


def test_mock_output_is_valid_schema():
    output = mock_observability_agent_output()
    assert isinstance(output, ObservabilityAgentOutput)
    dumped = output.model_dump(mode="json")
    assert "prometheus_configuration" in dumped
    assert "grafana_dashboards" in dumped
    assert "alert_rules" in dumped
    assert "logging_flows" in dumped
    assert "slo_definitions" in dumped


def test_run_request_defaults():
    request = ObservabilityRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"
    assert request.kubernetes_run_id is None


def test_run_request_with_kubernetes_run_id():
    request = ObservabilityRunRequest(requirement_id="req-1", kubernetes_run_id="k8s-1")
    assert request.kubernetes_run_id == "k8s-1"


@pytest.mark.parametrize("status", list(ObservabilityRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=90.0, errors=[], counts={"alert_rules": 5})
    assert result.is_valid is True


def test_output_roundtrip_serialization():
    original = mock_observability_agent_output()
    restored = ObservabilityAgentOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert ObservabilityRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert ObservabilityArtifactResponse.model_config.get("from_attributes") is True
