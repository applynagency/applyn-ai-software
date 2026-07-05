import pytest

from app.backend_code_review.validator import BackendCodeReviewValidator
from app.models.backend_code_review import BackendApprovalStatus
from app.schemas.backend_code_review import REVIEW_CATEGORIES, BackendCodeReviewOutput
from app.tests.conftest import mock_backend_code_review_output


@pytest.mark.parametrize("category", REVIEW_CATEGORIES)
def test_category_scores_contains_category(category):
    output = mock_backend_code_review_output()
    assert category in output.category_scores


@pytest.mark.parametrize("category", REVIEW_CATEGORIES)
def test_issue_category_validation_accepts_known_categories(category):
    output = mock_backend_code_review_output()
    data = output.model_dump(mode="json")
    data["issues"][0]["category"] = category
    result = BackendCodeReviewValidator().validate(BackendCodeReviewOutput(**data))
    assert result.is_valid is True


@pytest.mark.parametrize("category", REVIEW_CATEGORIES)
def test_recommendation_category_validation_accepts_known_categories(category):
    output = mock_backend_code_review_output()
    data = output.model_dump(mode="json")
    data["recommendations"][0]["category"] = category
    result = BackendCodeReviewValidator().validate(BackendCodeReviewOutput(**data))
    assert result.is_valid is True


@pytest.mark.parametrize("status", list(BackendApprovalStatus))
def test_validator_accepts_each_approval_status(status):
    output = mock_backend_code_review_output(approval_status=status)
    result = BackendCodeReviewValidator().validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("score", [0, 5, 10, 25, 40, 55, 70, 85, 95, 100])
def test_validator_accepts_boundary_review_scores(score):
    output = mock_backend_code_review_output(review_score=float(score))
    result = BackendCodeReviewValidator().validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("score", [-1, -5, 101, 120, 1000])
def test_validator_rejects_out_of_range_scores(score):
    output = mock_backend_code_review_output(review_score=float(score))
    result = BackendCodeReviewValidator().validate(output)
    assert result.is_valid is False


@pytest.mark.parametrize("index", list(range(0, 40)))
def test_mock_output_issue_and_recommendation_shapes(index):
    output = mock_backend_code_review_output()
    issue = output.issues[index % len(output.issues)]
    recommendation = output.recommendations[index % len(output.recommendations)]
    assert issue.id
    assert issue.category
    assert issue.title
    assert recommendation.id
    assert recommendation.category
    assert recommendation.title


@pytest.mark.parametrize("index", list(range(0, 40)))
def test_validator_counts_consistent(index):
    output = mock_backend_code_review_output()
    result = BackendCodeReviewValidator().validate(output)
    assert result.counts["issue_count"] == len(output.issues)
    assert result.counts["recommendation_count"] == len(output.recommendations)
    assert result.counts["category_score_count"] == len(output.category_scores)


@pytest.mark.parametrize("label", ["Architecture", "Security", "Performance", "Testing", "API Design"])
def test_summary_required_for_quality_signal(label):
    output = mock_backend_code_review_output(summary=f"{label} needs follow-up.")
    result = BackendCodeReviewValidator().validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("bad_summary", ["", " ", "  ", "\n", "\t"])
def test_blank_summary_fails_validation(bad_summary):
    output = mock_backend_code_review_output(summary=bad_summary)
    result = BackendCodeReviewValidator().validate(output)
    assert result.is_valid is False


@pytest.mark.parametrize("index", list(range(0, 44)))
def test_category_score_values_are_numeric(index):
    output = mock_backend_code_review_output()
    category = REVIEW_CATEGORIES[index % len(REVIEW_CATEGORIES)]
    assert isinstance(output.category_scores[category], float)
