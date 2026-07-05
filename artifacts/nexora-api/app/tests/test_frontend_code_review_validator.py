from app.frontend_code_review.validator import FrontendCodeReviewValidator
from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import (
    REVIEW_CATEGORIES,
    FrontendCodeReviewOutput,
)
from app.tests.conftest import mock_frontend_code_review_output


def test_validator_accepts_complete_output():
    validator = FrontendCodeReviewValidator()
    result = validator.validate(mock_frontend_code_review_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_review_score_above_100():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output(review_score=150.0)
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("review_score" in error for error in result.errors)


def test_validator_rejects_negative_review_score():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output(review_score=-5.0)
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("review_score" in error for error in result.errors)


def test_validator_rejects_missing_approval_status():
    validator = FrontendCodeReviewValidator()
    output = FrontendCodeReviewOutput.model_construct(
        review_score=85.0,
        approval_status=None,
        issues=[],
        recommendations=[],
        category_scores={category: 80.0 for category in REVIEW_CATEGORIES},
        summary="Valid summary text.",
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("approval_status" in error for error in result.errors)


def test_validator_rejects_invalid_issue_category():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output()
    data = output.model_dump()
    data["issues"][0]["category"] = "InvalidCategory"
    result = validator.validate(FrontendCodeReviewOutput(**data))
    assert result.is_valid is False
    assert any("issues" in error for error in result.errors)


def test_validator_rejects_empty_issue_category():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output()
    data = output.model_dump()
    data["issues"][0]["category"] = ""
    result = validator.validate(FrontendCodeReviewOutput(**data))
    assert result.is_valid is False
    assert any("issues" in error for error in result.errors)


def test_validator_rejects_invalid_recommendation_category():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output()
    data = output.model_dump()
    data["recommendations"][0]["category"] = "NotARealCategory"
    result = validator.validate(FrontendCodeReviewOutput(**data))
    assert result.is_valid is False
    assert any("recommendations" in error for error in result.errors)


def test_validator_rejects_empty_summary():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output(summary="   ")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("summary" in error for error in result.errors)


def test_validator_rejects_missing_category_scores():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output(category_scores={})
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("category_scores" in error for error in result.errors)


def test_validator_rejects_invalid_category_in_scores():
    validator = FrontendCodeReviewValidator()
    scores = {category: 80.0 for category in REVIEW_CATEGORIES}
    scores["Legacy jQuery"] = 70.0
    output = mock_frontend_code_review_output(category_scores=scores)
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("category_scores" in error for error in result.errors)


def test_validator_counts_are_reported():
    validator = FrontendCodeReviewValidator()
    result = validator.validate(mock_frontend_code_review_output())
    assert result.counts["issue_count"] >= 1
    assert result.counts["recommendation_count"] >= 1
    assert result.counts["category_score_count"] == len(REVIEW_CATEGORIES)
    assert result.counts["has_review_score"] is True
    assert result.counts["has_approval_status"] is True


def test_validator_accepts_empty_issues_and_recommendations():
    validator = FrontendCodeReviewValidator()
    output = mock_frontend_code_review_output(
        issues=[],
        recommendations=[],
        approval_status=ApprovalStatus.APPROVED,
    )
    result = validator.validate(output)
    assert result.is_valid is True
    assert result.counts["issue_count"] == 0
    assert result.counts["recommendation_count"] == 0
