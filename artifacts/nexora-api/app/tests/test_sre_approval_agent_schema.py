import pytest

from app.models.sre_approval import SreApprovalRunStatus, SreStatus
from app.schemas.sre_approval import (
    SreApprovalArtifactResponse,
    SreApprovalOutput,
    SreApprovalRunRequest,
    SreApprovalRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_sre_approval_output


def test_mock_output_is_valid_schema():
    output = mock_sre_approval_output()
    assert isinstance(output, SreApprovalOutput)
    dumped = output.model_dump(mode="json")
    assert dumped["sre_status"] in ("SRE_APPROVED", "SRE_APPROVED_WITH_WARNINGS", "SRE_REJECTED")
    for field in (
        "production_readiness_score",
        "availability_score",
        "security_score",
        "performance_score",
        "cost_score",
        "operational_readiness_score",
    ):
        assert field in dumped


def test_run_request_defaults():
    request = SreApprovalRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"
    assert request.kubernetes_run_id is None
    assert request.observability_run_id is None


def test_run_request_with_upstream_run_ids():
    request = SreApprovalRunRequest(requirement_id="req-1", kubernetes_run_id="k8s", observability_run_id="obs")
    assert request.kubernetes_run_id == "k8s"
    assert request.observability_run_id == "obs"


@pytest.mark.parametrize("status", list(SreApprovalRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


@pytest.mark.parametrize("status", list(SreStatus))
def test_sre_status_enum_values(status):
    assert status.value in ("SRE_APPROVED", "SRE_APPROVED_WITH_WARNINGS", "SRE_REJECTED")


def test_score_field_bounds_enforced():
    with pytest.raises(Exception):
        SreApprovalOutput(
            sre_status=SreStatus.SRE_APPROVED,
            production_readiness_score=150,
            availability_score=90,
            security_score=90,
            performance_score=90,
            cost_score=90,
            operational_readiness_score=90,
        )


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=95.0, errors=[], counts={"findings": 2})
    assert result.is_valid is True


def test_run_response_model_config():
    assert SreApprovalRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert SreApprovalArtifactResponse.model_config.get("from_attributes") is True
