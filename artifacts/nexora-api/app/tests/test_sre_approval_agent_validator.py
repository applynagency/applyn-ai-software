import pytest

from app.models.sre_approval import SreStatus
from app.schemas.sre_approval import SreApprovalOutput
from app.sre_approval.validator import SCORE_FIELDS, SreApprovalValidator
from app.tests.conftest import mock_sre_approval_output


@pytest.fixture
def validator():
    return SreApprovalValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_sre_approval_output())
    assert result.is_valid is True
    assert result.score >= 80


@pytest.mark.parametrize("status", list(SreStatus))
def test_all_statuses_valid(validator, status):
    output = mock_sre_approval_output(sre_status=status)
    result = validator.validate(output)
    assert result.is_valid is True


def test_empty_findings_fails(validator):
    output = mock_sre_approval_output(findings=[])
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("findings" in err for err in result.errors)


def test_empty_recommendation_fails(validator):
    output = mock_sre_approval_output(recommendation="")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("recommendation" in err for err in result.errors)


@pytest.mark.parametrize("field", list(SCORE_FIELDS))
def test_score_above_range_fails(validator, field):
    data = mock_sre_approval_output().model_dump()
    data[field] = 150
    result = validator.validate(SreApprovalOutput.model_construct(**{**data, "sre_status": SreStatus(data["sre_status"])}))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", list(SCORE_FIELDS))
def test_score_below_range_fails(validator, field):
    data = mock_sre_approval_output().model_dump()
    data[field] = -5
    result = validator.validate(SreApprovalOutput.model_construct(**{**data, "sre_status": SreStatus(data["sre_status"])}))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", list(SCORE_FIELDS))
def test_valid_scores_have_no_errors(validator, field):
    result = validator.validate(mock_sre_approval_output())
    assert not any(field in err for err in result.errors)


def test_score_fields_match_spec():
    assert set(SCORE_FIELDS) == {
        "production_readiness_score",
        "availability_score",
        "security_score",
        "performance_score",
        "cost_score",
        "operational_readiness_score",
    }


def test_valid_score_is_float(validator):
    result = validator.validate(mock_sre_approval_output())
    assert isinstance(result.score, float)
