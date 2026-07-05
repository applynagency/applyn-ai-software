from app.frontend_v3.prompt_builder import FrontendDeveloperV3PromptBuilder


def test_prompt_version():
    assert FrontendDeveloperV3PromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = FrontendDeveloperV3PromptBuilder.get_system_prompt()
    assert "50 generated_files" in prompt.lower() or "At least 50 generated_files" in prompt
    assert "package.json" in prompt
    assert "Dockerfile" in prompt


def test_user_prompt_includes_requirement_and_v2_output():
    prompt = FrontendDeveloperV3PromptBuilder.build_user_prompt(
        requirement_text="Build a dashboard",
        frontend_v2_output={"page_files": []},
    )
    assert "Build a dashboard" in prompt
    assert "Frontend Developer V2 Output" in prompt


def test_system_prompt_forbids_todo_placeholders():
    prompt = FrontendDeveloperV3PromptBuilder.get_system_prompt()
    assert "Do NOT use TODO or FIXME" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = FrontendDeveloperV3PromptBuilder.get_system_prompt()
    assert "generated_files" in prompt
    assert "project_structure" in prompt
    assert "docker_configuration" in prompt
