from app.uiux_designer.prompt_builder import UIUXPromptBuilder


def test_prompt_version():
    assert UIUXPromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = UIUXPromptBuilder.get_system_prompt()
    assert "5 screens" in prompt.lower() or "At least 5 screens" in prompt
    assert "user flows" in prompt.lower()


def test_user_prompt_includes_requirement_and_ba_output():
    prompt = UIUXPromptBuilder.build_user_prompt(
        requirement_text="Build a dashboard",
        business_analyst_output={"functional_requirements": []},
    )
    assert "Build a dashboard" in prompt
    assert "Business Analyst Output" in prompt


def test_system_prompt_forbids_react_code():
    prompt = UIUXPromptBuilder.get_system_prompt()
    assert "Do NOT generate React code" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = UIUXPromptBuilder.get_system_prompt()
    assert "information_architecture" in prompt
    assert "frontend_handoff" in prompt
    assert "accessibility_guidelines" in prompt
