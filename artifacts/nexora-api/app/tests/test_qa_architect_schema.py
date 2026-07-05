import pytest

from app.models.qa_architect import QAArchitectRunStatus
from app.schemas.qa_architect import (
    QAArchitectArtifactResponse,
    QAArchitectOutput,
    QAArchitectRunRequest,
    QAArchitectRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_qa_architect_output


def test_output_schema_defaults():
    output = QAArchitectOutput()
    assert output.test_strategy == ""
    assert output.test_coverage_matrix == []
    assert output.risk_areas == []


def test_mock_output_is_valid_schema():
    output = mock_qa_architect_output()
    assert isinstance(output, QAArchitectOutput)
    dumped = output.model_dump()
    assert len(dumped["test_coverage_matrix"]) >= 10
    assert len(dumped["risk_areas"]) >= 5


def test_run_request_defaults():
    request = QAArchitectRunRequest(requirement_id="req-1")
    assert request.frontend_execution_run_id is None
    assert request.backend_execution_run_id is None


@pytest.mark.parametrize("status", list(QAArchitectRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(
        is_valid=True,
        score=96.5,
        errors=[],
        counts={"test_scenarios": 10},
    )
    assert result.is_valid is True
    assert result.score == 96.5


def test_output_roundtrip_serialization():
    original = mock_qa_architect_output()
    restored = QAArchitectOutput(**original.model_dump())
    assert restored.model_dump() == original.model_dump()


def test_run_response_model_config():
    assert QAArchitectRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert QAArchitectArtifactResponse.model_config.get("from_attributes") is True
