from app.frontend_code_review.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_code_review_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "# Frontend Code Review" in md


def test_markdown_includes_review_score():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "**Review Score:**" in md
    assert "86.5" in md


def test_markdown_includes_approval_status():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "**Approval Status:**" in md
    assert "APPROVED_WITH_WARNINGS" in md


def test_markdown_includes_summary_section():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "## Summary" in md


def test_markdown_includes_category_scores_section():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "## Category Scores" in md


def test_markdown_includes_issues_section():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "## Issues" in md


def test_markdown_includes_recommendations_section():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "## Recommendations" in md


def test_markdown_includes_issue_details():
    md = output_to_markdown(mock_frontend_code_review_output())
    assert "Missing strict null checks" in md
    assert "ISS-001" in md
