import pytest

from app.models.qa_approval import QAApprovalRunStatus
from app.schemas.qa_approval import (
    QAApprovalArtifactResponse,
    QAApprovalOutput,
    QAApprovalRunRequest,
    QAApprovalRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_qa_approval_output


def test_mock_output_is_valid_schema():
    output = mock_qa_approval_output()
    assert isinstance(output, QAApprovalOutput)
    dumped = output.model_dump(mode="json")
    assert "qa_status" in dumped
    assert "quality_score" in dumped
    assert "findings" in dumped
    assert "warnings" in dumped
    assert "recommendation" in dumped



def test_run_request_defaults():
    request = QAApprovalRunRequest(requirement_id="req-1")
    assert request.requirement_id == "req-1"


@pytest.mark.parametrize("status", list(QAApprovalRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=96.5, errors=[], counts={"sample": 1})
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_qa_approval_output()
    restored = QAApprovalOutput(**original.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_run_response_model_config():
    assert QAApprovalRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert QAApprovalArtifactResponse.model_config.get("from_attributes") is True
