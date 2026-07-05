from app.frontend_v2.prompt_builder import FrontendDeveloperV2PromptBuilder


def test_prompt_version():
    assert FrontendDeveloperV2PromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = FrontendDeveloperV2PromptBuilder.get_system_prompt()
    assert "10 page_files" in prompt.lower() or "At least 10 page_files" in prompt
    assert "20 component_files" in prompt.lower() or "At least 20 component_files" in prompt


def test_user_prompt_includes_requirement_and_v1_output():
    prompt = FrontendDeveloperV2PromptBuilder.build_user_prompt(
        requirement_text="Build a dashboard",
        frontend_v1_output={"page_structure": []},
    )
    assert "Build a dashboard" in prompt
    assert "Frontend Developer V1 Output" in prompt


def test_system_prompt_forbids_react_code():
    prompt = FrontendDeveloperV2PromptBuilder.get_system_prompt()
    assert "Do NOT generate React code" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = FrontendDeveloperV2PromptBuilder.get_system_prompt()
    assert "file_structure" in prompt
    assert "page_files" in prompt
    assert "service_files" in prompt
