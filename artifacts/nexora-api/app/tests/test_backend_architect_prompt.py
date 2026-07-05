from app.backend_architect.prompt_builder import BackendArchitectPromptBuilder


def test_prompt_version():
    assert BackendArchitectPromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_minimums():
    prompt = BackendArchitectPromptBuilder.get_system_prompt()
    assert "10 api endpoints" in prompt.lower() or "at least 10 api" in prompt.lower()
    assert "10 database entities" in prompt.lower() or "at least 10 database" in prompt.lower()
    assert "3 integrations" in prompt.lower() or "at least 3 integrations" in prompt.lower()
    assert "3 security controls" in prompt.lower()
    assert "3 user roles" in prompt.lower()


def test_user_prompt_includes_requirement_and_ba_output():
    prompt = BackendArchitectPromptBuilder.build_user_prompt(
        requirement_text="Build a payment API",
        business_analyst_output={"functional_requirements": []},
    )
    assert "Build a payment API" in prompt
    assert "Business Analyst Output" in prompt


def test_system_prompt_forbids_source_code():
    prompt = BackendArchitectPromptBuilder.get_system_prompt()
    assert "Do NOT generate application source code" in prompt


def test_system_prompt_lists_output_schema_keys():
    prompt = BackendArchitectPromptBuilder.get_system_prompt()
    assert "api_architecture" in prompt
    assert "database_architecture" in prompt
    assert "security_architecture" in prompt
    assert "development_guidelines" in prompt
