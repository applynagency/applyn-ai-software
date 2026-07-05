from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import REVIEW_CATEGORIES, FrontendCodeReviewOutput
from app.tests.conftest import mock_frontend_code_review_output


def test_output_schema_defaults():
    output = FrontendCodeReviewOutput(
        review_score=0.0,
        approval_status=ApprovalStatus.NEEDS_REVIEW,
    )
    assert output.issues == []
    assert output.recommendations == []
    assert output.category_scores == {}
    assert output.summary == ""


def test_mock_output_is_valid_schema():
    output = mock_frontend_code_review_output()
    assert isinstance(output, FrontendCodeReviewOutput)
    dumped = output.model_dump()
    assert len(dumped["issues"]) >= 1
    assert len(dumped["recommendations"]) >= 1


def test_output_serializes_issues():
    output = mock_frontend_code_review_output()
    issues = output.model_dump()["issues"]
    assert all(
        key in issue
        for issue in issues
        for key in ("id", "category", "severity", "title", "description")
    )


def test_output_serializes_recommendations():
    output = mock_frontend_code_review_output()
    recommendations = output.model_dump()["recommendations"]
    assert all(
        key in rec
        for rec in recommendations
        for key in ("id", "category", "title", "description", "priority")
    )


def test_output_serializes_category_scores():
    output = mock_frontend_code_review_output()
    scores = output.model_dump()["category_scores"]
    assert len(scores) == len(REVIEW_CATEGORIES)
    assert all(category in scores for category in REVIEW_CATEGORIES)
