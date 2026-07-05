from app.frontend_code_review.prompt_builder import FrontendCodeReviewPromptBuilder


def test_prompt_version():
    assert FrontendCodeReviewPromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_review_categories():
    prompt = FrontendCodeReviewPromptBuilder.get_system_prompt()
    assert "TypeScript" in prompt
    assert "Accessibility" in prompt
    assert "Code Quality" in prompt


def test_system_prompt_mentions_approval_statuses():
    prompt = FrontendCodeReviewPromptBuilder.get_system_prompt()
    assert "APPROVED" in prompt
    assert "APPROVED_WITH_WARNINGS" in prompt
    assert "NEEDS_REVIEW" in prompt
    assert "REJECTED" in prompt


def test_user_prompt_includes_requirement_and_v3_output():
    prompt = FrontendCodeReviewPromptBuilder.build_user_prompt(
        requirement_text="Build a dashboard",
        frontend_v3_output={"generated_files": []},
    )
    assert "Build a dashboard" in prompt
    assert "Frontend Developer V3 Output" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = FrontendCodeReviewPromptBuilder.get_system_prompt()
    assert "review_score" in prompt
    assert "category_scores" in prompt
    assert "issues" in prompt
    assert "recommendations" in prompt
