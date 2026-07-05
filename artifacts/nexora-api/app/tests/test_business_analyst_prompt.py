from app.business_analyst.prompt_builder import BusinessAnalystPromptBuilder


def test_prompt_version_defined():
    assert BusinessAnalystPromptBuilder.get_prompt_version() == "1.0.0"


def test_system_prompt_mentions_business_analysis():
    prompt = BusinessAnalystPromptBuilder.get_system_prompt()
    assert "Business Analyst" in prompt
    assert "functional_requirements" in prompt


def test_user_prompt_includes_requirement():
    prompt = BusinessAnalystPromptBuilder.build_user_prompt(
        requirement_text="Build a CRM",
        product_owner_output={"project_summary": "CRM project"},
    )
    assert "Build a CRM" in prompt
    assert "CRM project" in prompt


def test_user_prompt_includes_po_output():
    prompt = BusinessAnalystPromptBuilder.build_user_prompt(
        requirement_text="Req",
        product_owner_output={"epics": [{"name": "Auth"}]},
    )
    assert "Auth" in prompt
