from app.backend_code_review.validator import BackendCodeReviewValidator
from app.models.backend_code_review import BackendApprovalStatus
from app.schemas.backend_code_review import REVIEW_CATEGORIES, BackendCodeReviewOutput
from app.tests.conftest import mock_backend_code_review_output


def test_validator_accepts_complete_output():
    validator = BackendCodeReviewValidator()
    result = validator.validate(mock_backend_code_review_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_review_score_above_100():
    validator = BackendCodeReviewValidator()
    output = mock_backend_code_review_output(review_score=150.0)
    result = validator.validate(output)
    assert result.is_valid is False


def test_validator_rejects_invalid_issue_category():
    validator = BackendCodeReviewValidator()
    output = mock_backend_code_review_output()
    data = output.model_dump()
    data["issues"][0]["category"] = "Unknown"
    result = validator.validate(BackendCodeReviewOutput(**data))
    assert result.is_valid is False


def test_validator_rejects_missing_summary():
    validator = BackendCodeReviewValidator()
    output = mock_backend_code_review_output(summary=" ")
    result = validator.validate(output)
    assert result.is_valid is False


def test_validator_counts_are_reported():
    validator = BackendCodeReviewValidator()
    result = validator.validate(mock_backend_code_review_output())
    assert result.counts["issue_count"] >= 1
    assert result.counts["recommendation_count"] >= 1
    assert result.counts["category_score_count"] == len(REVIEW_CATEGORIES)
    assert result.counts["has_review_score"] is True
    assert result.counts["has_approval_status"] is True


def test_validator_accepts_empty_issues_and_recommendations():
    validator = BackendCodeReviewValidator()
    output = mock_backend_code_review_output(
        issues=[],
        recommendations=[],
        approval_status=BackendApprovalStatus.APPROVED,
    )
    result = validator.validate(output)
    assert result.is_valid is True
