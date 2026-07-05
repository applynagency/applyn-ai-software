import pytest

from app.models.unit_test import UnitTestRunStatus
from app.schemas.unit_test import (
    UnitTestArtifactResponse,
    UnitTestGeneratorOutput,
    UnitTestRunRequest,
    UnitTestRunResponse,
    ValidationResult,
)
from app.tests.conftest import mock_unit_test_generator_output


def test_output_schema_defaults():
    output = UnitTestGeneratorOutput()
    assert output.frontend_unit_test_specifications == []
    assert output.backend_unit_test_specifications == []
    assert output.test_fixtures == []


def test_mock_output_is_valid_schema():
    output = mock_unit_test_generator_output()
    assert isinstance(output, UnitTestGeneratorOutput)
    dumped = output.model_dump()
    assert len(dumped["frontend_unit_test_specifications"]) >= 5
    assert len(dumped["backend_unit_test_specifications"]) >= 5


def test_run_request_defaults():
    request = UnitTestRunRequest(requirement_id="req-1")
    assert request.qa_architect_run_id is None


@pytest.mark.parametrize("status", list(UnitTestRunStatus))
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(
        is_valid=True,
        score=92.0,
        errors=[],
        counts={"frontend_specs": 5},
    )
    assert result.is_valid is True
    assert result.score == 92.0


def test_output_roundtrip_serialization():
    original = mock_unit_test_generator_output()
    restored = UnitTestGeneratorOutput(**original.model_dump())
    assert restored.model_dump() == original.model_dump()


def test_run_response_model_config():
    assert UnitTestRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert UnitTestArtifactResponse.model_config.get("from_attributes") is True
