from app.backend_code_review.markdown import output_to_markdown
from app.backend_code_review.prompt_builder import BackendCodeReviewPromptBuilder
from app.tests.conftest import mock_backend_code_review_output


def test_prompt_version():
    assert BackendCodeReviewPromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_review_categories():
    prompt = BackendCodeReviewPromptBuilder.get_system_prompt()
    assert "Architecture" in prompt
    assert "FastAPI" in prompt
    assert "Database Design" in prompt


def test_system_prompt_mentions_approval_statuses():
    prompt = BackendCodeReviewPromptBuilder.get_system_prompt()
    assert "APPROVED" in prompt
    assert "APPROVED_WITH_WARNINGS" in prompt
    assert "NEEDS_REVIEW" in prompt
    assert "REJECTED" in prompt


def test_markdown_includes_core_sections():
    md = output_to_markdown(mock_backend_code_review_output())
    assert "# Backend Code Review" in md
    assert "## Summary" in md
    assert "## Category Scores" in md
    assert "## Issues" in md
    assert "## Recommendations" in md
