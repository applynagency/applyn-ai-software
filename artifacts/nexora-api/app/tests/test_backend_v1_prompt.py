from app.backend_v1.prompt_builder import BackendDeveloperV1PromptBuilder


def test_prompt_version():
    assert BackendDeveloperV1PromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = BackendDeveloperV1PromptBuilder.get_system_prompt()
    assert "10 service specifications" in prompt.lower()
    assert "10 repository specifications" in prompt.lower()
    assert "10 api specifications" in prompt.lower()
    assert "10 database model specifications" in prompt.lower()
    assert "3 integration specifications" in prompt.lower()
    assert "3 background job specifications" in prompt.lower()
    assert "3 user roles" in prompt.lower()


def test_user_prompt_includes_requirement_and_ba_output():
    prompt = BackendDeveloperV1PromptBuilder.build_user_prompt(
        requirement_text="Build a REST API",
        backend_architect_output={"api_architecture": []},
    )
    assert "Build a REST API" in prompt
    assert "Backend Architect Output" in prompt


def test_system_prompt_forbids_source_code():
    prompt = BackendDeveloperV1PromptBuilder.get_system_prompt()
    assert "Do NOT generate FastAPI source code" in prompt
    assert "Implementation specifications only" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = BackendDeveloperV1PromptBuilder.get_system_prompt()
    assert "service_specifications" in prompt
    assert "repository_specifications" in prompt
    assert "api_specifications" in prompt
    assert "database_model_specifications" in prompt
    assert "authentication_specifications" in prompt
    assert "authorization_specifications" in prompt
    assert "validation_specifications" in prompt
    assert "background_job_specifications" in prompt
    assert "integration_specifications" in prompt
    assert "folder_structure" in prompt
    assert "module_breakdown" in prompt
    assert "implementation_guidelines" in prompt


def test_system_prompt_requires_json_only():
    prompt = BackendDeveloperV1PromptBuilder.get_system_prompt()
    assert "Return ONLY the JSON object" in prompt


def test_user_prompt_includes_ba_json_payload():
    prompt = BackendDeveloperV1PromptBuilder.build_user_prompt(
        requirement_text="Test",
        backend_architect_output={"backend_stack": {"framework": "FastAPI"}},
    )
    assert "FastAPI" in prompt
