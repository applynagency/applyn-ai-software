from app.backend_v2.prompt_builder import BackendDeveloperV2PromptBuilder


def test_prompt_version():
    assert BackendDeveloperV2PromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = BackendDeveloperV2PromptBuilder.get_system_prompt()
    assert "20 total files" in prompt.lower() or "at least 20 total files" in prompt.lower()
    assert "10 router files" in prompt.lower() or "at least 10 router files" in prompt.lower()
    assert "10 schema files" in prompt.lower() or "at least 10 schema files" in prompt.lower()
    assert "10 model files" in prompt.lower() or "at least 10 model files" in prompt.lower()
    assert "10 repository files" in prompt.lower() or "at least 10 repository files" in prompt.lower()
    assert "10 service files" in prompt.lower() or "at least 10 service files" in prompt.lower()
    assert "5 middleware files" in prompt.lower() or "at least 5 middleware files" in prompt.lower()
    assert "5 integration files" in prompt.lower() or "at least 5 integration files" in prompt.lower()
    assert "10 test files" in prompt.lower() or "at least 10 test files" in prompt.lower()


def test_user_prompt_includes_requirement_and_v1_output():
    prompt = BackendDeveloperV2PromptBuilder.build_user_prompt(
        requirement_text="Build a REST API",
        backend_v1_output={"api_specifications": []},
    )
    assert "Build a REST API" in prompt
    assert "Backend Developer V1 Output" in prompt


def test_system_prompt_forbids_source_code():
    prompt = BackendDeveloperV2PromptBuilder.get_system_prompt()
    assert "Do NOT generate FastAPI source code" in prompt
    assert "File-level specifications only" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = BackendDeveloperV2PromptBuilder.get_system_prompt()
    assert "file_structure" in prompt
    assert "router_files" in prompt
    assert "schema_files" in prompt
    assert "model_files" in prompt
    assert "repository_files" in prompt
    assert "service_files" in prompt
    assert "dependency_files" in prompt
    assert "middleware_files" in prompt
    assert "background_job_files" in prompt
    assert "integration_files" in prompt
    assert "configuration_files" in prompt
    assert "migration_files" in prompt
    assert "test_files" in prompt
    assert "infrastructure_files" in prompt


def test_system_prompt_requires_json_only():
    prompt = BackendDeveloperV2PromptBuilder.get_system_prompt()
    assert "Return ONLY the JSON object" in prompt


def test_user_prompt_includes_v1_json_payload():
    prompt = BackendDeveloperV2PromptBuilder.build_user_prompt(
        requirement_text="Test",
        backend_v1_output={"folder_structure": {"root": "app"}},
    )
    assert "app" in prompt
