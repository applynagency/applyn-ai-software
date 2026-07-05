from app.performance_test.prompt_builder import PerformanceTestPromptBuilder


def test_prompt_version():
    builder = PerformanceTestPromptBuilder()
    assert builder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums_or_constraints():
    builder = PerformanceTestPromptBuilder()
    prompt = builder.get_system_prompt().lower()
    assert "return valid json only" in prompt
    assert "load_test_plan" in prompt
    assert "5" in prompt
    assert "stress_test_plan" in prompt
    assert "3" in prompt
    assert "performance_bottlenecks" in prompt
    assert "3" in prompt
    assert "scaling_recommendations" in prompt
    assert "3" in prompt
    assert "caching_recommendations" in prompt
    assert "3" in prompt



def test_user_prompt_includes_requirement_and_prereqs():
    builder = PerformanceTestPromptBuilder()
    prompt = builder.build_user_prompt(requirement_text="Build checkout flow", integration_test_output={"status": "ok"}, security_test_output={"status": "ok"})
    assert "Build checkout flow" in prompt
    assert "Integration Test Output" in prompt
    assert "Security Test Output" in prompt



def test_system_prompt_forbids_markdown_output():
    builder = PerformanceTestPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "Return valid JSON only" in prompt
