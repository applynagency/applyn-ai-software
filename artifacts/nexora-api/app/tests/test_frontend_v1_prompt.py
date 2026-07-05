from app.frontend_v1.prompt_builder import FrontendDeveloperV1PromptBuilder


def test_prompt_version():
    assert FrontendDeveloperV1PromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = FrontendDeveloperV1PromptBuilder.get_system_prompt()
    assert "10 pages" in prompt.lower() or "At least 10 pages" in prompt
    assert "20 components" in prompt.lower() or "At least 20 components" in prompt


def test_user_prompt_includes_requirement_and_fa_output():
    prompt = FrontendDeveloperV1PromptBuilder.build_user_prompt(
        requirement_text="Build a dashboard",
        frontend_architect_output={"page_architecture": []},
    )
    assert "Build a dashboard" in prompt
    assert "Frontend Architect Output" in prompt


def test_system_prompt_forbids_react_code():
    prompt = FrontendDeveloperV1PromptBuilder.get_system_prompt()
    assert "Do NOT generate React code" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = FrontendDeveloperV1PromptBuilder.get_system_prompt()
    assert "project_structure" in prompt
    assert "module_breakdown" in prompt
    assert "state_management" in prompt
