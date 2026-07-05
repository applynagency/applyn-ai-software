import pytest

from app.models.kubernetes_agent import KubernetesRunStatus
from app.schemas.kubernetes_agent import (
    KubernetesAgentOutput,
    KubernetesArtifactResponse,
    KubernetesRunRequest,
    KubernetesRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_kubernetes_agent_output


def test_mock_output_is_valid_schema():
    output = mock_kubernetes_agent_output()
    assert isinstance(output, KubernetesAgentOutput)
    dumped = output.model_dump(mode="json")
    assert "deployments" in dumped
    assert "services" in dumped
    assert "ingresses" in dumped
    assert "hpas" in dumped
    assert "configmaps_secrets" in dumped
    assert "network_policies" in dumped
    assert "environment_overlays" in dumped


def test_run_request_defaults():
    request = KubernetesRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"
    assert request.cicd_run_id is None


def test_run_request_with_cicd_run_id():
    request = KubernetesRunRequest(requirement_id="req-1", cicd_run_id="cicd-1")
    assert request.cicd_run_id == "cicd-1"


@pytest.mark.parametrize("status", list(KubernetesRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"deployments": 3})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_kubernetes_agent_output()
    restored = KubernetesAgentOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert KubernetesRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert KubernetesArtifactResponse.model_config.get("from_attributes") is True
