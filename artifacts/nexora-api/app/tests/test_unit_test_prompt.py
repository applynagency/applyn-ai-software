from app.unit_test_generator.prompt_builder import UnitTestGeneratorPromptBuilder


def test_prompt_version():
    builder = UnitTestGeneratorPromptBuilder()
    assert builder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    builder = UnitTestGeneratorPromptBuilder()
    prompt = builder.get_system_prompt().lower()
    assert "frontend_unit_test_specifications" in prompt
    assert "backend_unit_test_specifications" in prompt
    assert "test_fixtures: 3" in builder.get_system_prompt()


def test_user_prompt_includes_requirement_and_qa_output():
    builder = UnitTestGeneratorPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Build search page",
        qa_architect_output={"test_strategy": "risk-based"},
    )
    assert "Build search page" in prompt
    assert "QA Architect Output" in prompt


def test_system_prompt_forbids_markdown_output():
    builder = UnitTestGeneratorPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "Return valid JSON only" in prompt
