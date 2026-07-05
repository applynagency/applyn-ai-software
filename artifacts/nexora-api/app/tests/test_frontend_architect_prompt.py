from app.frontend_architect.prompt_builder import FrontendArchitectPromptBuilder


def test_prompt_version():
    assert FrontendArchitectPromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = FrontendArchitectPromptBuilder.get_system_prompt()
    assert "10 pages" in prompt.lower() or "at least 10 pages" in prompt.lower()
    assert "20 components" in prompt.lower() or "at least 20 components" in prompt.lower()
    assert "api integration" in prompt.lower()


def test_user_prompt_includes_requirement_and_uiux_output():
    prompt = FrontendArchitectPromptBuilder.build_user_prompt(
        requirement_text="Build a dashboard",
        uiux_output={"screen_inventory": []},
    )
    assert "Build a dashboard" in prompt
    assert "UI/UX Designer Output" in prompt


def test_system_prompt_forbids_react_code():
    prompt = FrontendArchitectPromptBuilder.get_system_prompt()
    assert "Do NOT generate React code" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = FrontendArchitectPromptBuilder.get_system_prompt()
    assert "page_architecture" in prompt
    assert "component_architecture" in prompt
    assert "development_guidelines" in prompt
