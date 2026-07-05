from app.integration_test.prompt_builder import IntegrationTestPromptBuilder


def test_prompt_version():
    builder = IntegrationTestPromptBuilder()
    assert builder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums_or_constraints():
    builder = IntegrationTestPromptBuilder()
    prompt = builder.get_system_prompt().lower()
    assert "return valid json only" in prompt
    assert "api_test_cases" in prompt
    assert "8" in prompt
    assert "frontend_backend_flows" in prompt
    assert "5" in prompt
    assert "database_validation" in prompt
    assert "5" in prompt



def test_user_prompt_includes_requirement_and_prereqs():
    builder = IntegrationTestPromptBuilder()
    prompt = builder.build_user_prompt(requirement_text="Build checkout flow", frontend_execution_output={"status": "ok"}, backend_execution_output={"status": "ok"}, unit_test_output={"status": "ok"})
    assert "Build checkout flow" in prompt
    assert "Frontend Execution Output" in prompt
    assert "Backend Execution Output" in prompt
    assert "Unit Test Output" in prompt



def test_system_prompt_forbids_markdown_output():
    builder = IntegrationTestPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "Return valid JSON only" in prompt
