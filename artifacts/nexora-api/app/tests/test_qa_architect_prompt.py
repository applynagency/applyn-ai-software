from app.qa_architect.prompt_builder import QAArchitectPromptBuilder


def test_prompt_version():
    builder = QAArchitectPromptBuilder()
    assert builder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    builder = QAArchitectPromptBuilder()
    prompt = builder.get_system_prompt().lower()
    assert "10 scenarios" in prompt
    assert "risk_areas: 5" in prompt or "risk_areas: 5" in builder.get_system_prompt()
    assert "acceptance_test_plan: 5" in builder.get_system_prompt()
    assert "regression_areas: 5" in builder.get_system_prompt()


def test_user_prompt_includes_requirement_and_prereqs():
    builder = QAArchitectPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Build checkout flow",
        frontend_execution_output={"build_status": "success"},
        backend_execution_output={"build_status": "success"},
    )
    assert "Build checkout flow" in prompt
    assert "Frontend Execution Output" in prompt
    assert "Backend Execution Output" in prompt


def test_system_prompt_forbids_markdown_output():
    builder = QAArchitectPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "Return valid JSON only" in prompt
