from app.qa_approval.prompt_builder import QAApprovalPromptBuilder


def test_prompt_version():
    builder = QAApprovalPromptBuilder()
    assert builder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums_or_constraints():
    builder = QAApprovalPromptBuilder()
    prompt = builder.get_system_prompt().lower()
    assert "return valid json only" in prompt
    assert "findings" in prompt
    assert "1" in prompt



def test_user_prompt_includes_requirement_and_prereqs():
    builder = QAApprovalPromptBuilder()
    prompt = builder.build_user_prompt(requirement_text="Build checkout flow", integration_test_output={"status": "ok"}, security_test_output={"status": "ok"}, performance_test_output={"status": "ok"})
    assert "Build checkout flow" in prompt
    assert "Integration Test Output" in prompt
    assert "Security Test Output" in prompt
    assert "Performance Test Output" in prompt



def test_system_prompt_forbids_markdown_output():
    builder = QAApprovalPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "Return valid JSON only" in prompt
