from app.frontend_code_review.markdown import output_to_markdown
from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import REVIEW_CATEGORIES, FrontendCodeReviewOutput
from app.tests.conftest import mock_frontend_code_review_output


def test_markdown_includes_issue_severity():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "**Severity:**" in md
    assert "major" in md


def test_markdown_includes_file_path():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "src/components/Button.tsx" in md


def test_markdown_includes_issue_recommendation():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "optional chaining" in md


def test_markdown_shows_no_issues_message():
    output = mock_frontend_code_review_output(issues=[])
    md = output_to_markdown(output)
    assert "_No issues found._" in md


def test_markdown_shows_no_recommendations_message():
    output = mock_frontend_code_review_output(recommendations=[])
    md = output_to_markdown(output)
    assert "_No recommendations._" in md


def test_markdown_lists_all_review_categories():
    output = FrontendCodeReviewOutput(
        review_score=90.0,
        approval_status=ApprovalStatus.APPROVED,
        issues=[],
        recommendations=[],
        category_scores={category: 90.0 for category in REVIEW_CATEGORIES},
        summary="All categories scored.",
    )
    md = output_to_markdown(output)
    for category in REVIEW_CATEGORIES:
        assert category in md
