from app.security_test.prompt_builder import SecurityTestPromptBuilder


def test_prompt_version():
    builder = SecurityTestPromptBuilder()
    assert builder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums_or_constraints():
    builder = SecurityTestPromptBuilder()
    prompt = builder.get_system_prompt().lower()
    assert "return valid json only" in prompt
    assert "owasp_assessment" in prompt
    assert "5" in prompt
    assert "authentication_review" in prompt
    assert "3" in prompt
    assert "authorization_review" in prompt
    assert "3" in prompt
    assert "input_validation_review" in prompt
    assert "3" in prompt
    assert "dependency_security_scan" in prompt
    assert "3" in prompt
    assert "secrets_exposure_review" in prompt
    assert "3" in prompt



def test_user_prompt_includes_requirement_and_prereqs():
    builder = SecurityTestPromptBuilder()
    prompt = builder.build_user_prompt(requirement_text="Build checkout flow", frontend_execution_output={"status": "ok"}, backend_execution_output={"status": "ok"}, integration_test_output={"status": "ok"})
    assert "Build checkout flow" in prompt
    assert "Frontend Execution Output" in prompt
    assert "Backend Execution Output" in prompt
    assert "Integration Test Output" in prompt



def test_system_prompt_forbids_markdown_output():
    builder = SecurityTestPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "Return valid JSON only" in prompt
