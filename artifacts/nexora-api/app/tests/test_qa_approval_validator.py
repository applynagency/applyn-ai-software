import pytest

from app.models.qa_approval import QAStatus
from app.qa_approval.validator import ALLOWED_QA_STATUSES, QAApprovalValidator
from app.schemas.qa_approval import QAApprovalOutput
from app.tests.conftest import mock_qa_approval_output


@pytest.fixture
def validator():
    return QAApprovalValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_qa_approval_output())
    assert result.is_valid is True
    assert result.score == 100


def test_quality_score_out_of_range_fails(validator):
    with pytest.raises(Exception):
        QAApprovalOutput(**(mock_qa_approval_output().model_dump(mode="json") | {"quality_score": -1}))


def test_empty_findings_fails(validator):
    output = mock_qa_approval_output(findings=[])
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("findings" in err for err in result.errors)


def test_empty_recommendation_fails(validator):
    output = mock_qa_approval_output(recommendation="   ")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("recommendation" in err for err in result.errors)


@pytest.mark.parametrize("status", list(ALLOWED_QA_STATUSES))
def test_allowed_statuses_pass(validator, status):
    output = mock_qa_approval_output(qa_status=status.value)
    result = validator.validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("bad_score", [-5, -1, 101, 150])
def test_invalid_quality_scores_fail(validator, bad_score):
    with pytest.raises(Exception):
        QAApprovalOutput(**(mock_qa_approval_output().model_dump(mode="json") | {"quality_score": bad_score}))


@pytest.mark.parametrize("findings", [[], ["only one"], ["a", "b", "c"]])
def test_findings_rules(validator, findings):
    output = mock_qa_approval_output(findings=findings)
    result = validator.validate(output)
    if findings:
        assert result.is_valid is True
    else:
        assert result.is_valid is False


@pytest.mark.parametrize("warnings", [[], ["warn 1"], ["warn 1", "warn 2"]])
def test_warnings_are_optional(validator, warnings):
    output = mock_qa_approval_output(warnings=warnings)
    result = validator.validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("status", [QAStatus.QA_APPROVED, QAStatus.QA_APPROVED_WITH_WARNINGS, QAStatus.QA_REJECTED])
def test_status_enum_roundtrip(validator, status):
    output = mock_qa_approval_output(qa_status=status.value)
    result = validator.validate(output)
    assert result.counts["findings"] >= 1


@pytest.mark.parametrize("blank_text", ["", " ", "\n", "\t"])
def test_recommendation_blank_variants_fail(validator, blank_text):
    output = mock_qa_approval_output(recommendation=blank_text)
    result = validator.validate(output)
    assert result.is_valid is False


@pytest.mark.parametrize("score", [0, 1, 50, 99, 100])
def test_quality_score_boundaries_pass(validator, score):
    output = mock_qa_approval_output(quality_score=score)
    result = validator.validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("status", ["INVALID", "PENDING", "APPROVE", "REVIEW"]) 
def test_unknown_status_fails_schema_or_validator(validator, status):
    with pytest.raises(Exception):
        QAApprovalOutput(**(mock_qa_approval_output().model_dump(mode="json") | {"qa_status": status}))


def test_score_is_rounded(validator):
    result = validator.validate(mock_qa_approval_output())
    assert result.score == round(result.score, 2)


def test_score_never_negative(validator):
    output = mock_qa_approval_output(quality_score=0, findings=[], recommendation="")
    result = validator.validate(output)
    assert result.score >= 0


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_counts_track_findings_length(validator, n):
    output = mock_qa_approval_output(findings=[f"finding {i}" for i in range(n)])
    result = validator.validate(output)
    assert result.counts["findings"] == n


@pytest.mark.parametrize("n", [0, 1, 2, 4])
def test_counts_track_warnings_length(validator, n):
    output = mock_qa_approval_output(warnings=[f"warning {i}" for i in range(n)])
    result = validator.validate(output)
    assert result.counts["warnings"] == n


@pytest.mark.parametrize("quality_score,expected_valid", [(92, True), (75, True), (45, True), (0, True)])
def test_quality_score_values_remain_valid(validator, quality_score, expected_valid):
    output = mock_qa_approval_output(quality_score=quality_score)
    result = validator.validate(output)
    assert result.is_valid is expected_valid


@pytest.mark.parametrize("recommendation", ["Ship", "Ship with warnings", "Block release"]) 
def test_recommendation_text_passes(validator, recommendation):
    output = mock_qa_approval_output(recommendation=recommendation)
    result = validator.validate(output)
    assert result.is_valid is True


def test_multiple_errors_lower_score(validator):
    output = mock_qa_approval_output(findings=[], recommendation="")
    result = validator.validate(output)
    assert result.is_valid is False
    assert len(result.errors) >= 2
    assert result.score < 80
