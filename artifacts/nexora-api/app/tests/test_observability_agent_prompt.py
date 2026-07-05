from app.observability_agent.prompt_builder import ObservabilityAgentPromptBuilder


def test_prompt_version_present():
    builder = ObservabilityAgentPromptBuilder()
    assert builder.get_prompt_version()


def test_system_prompt_not_empty():
    builder = ObservabilityAgentPromptBuilder()
    assert len(builder.get_system_prompt()) > 20


def test_user_prompt_includes_requirement():
    builder = ObservabilityAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Observe platform",
        kubernetes_output={"deployments": "k8s-marker"},
    )
    assert "Observe platform" in prompt


def test_user_prompt_includes_kubernetes_output():
    builder = ObservabilityAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Req",
        kubernetes_output={"deployments": "k8s-marker"},
    )
    assert "k8s-marker" in prompt


def test_system_prompt_mentions_constraints():
    builder = ObservabilityAgentPromptBuilder()
    prompt = builder.get_system_prompt().lower()
    assert "alert" in prompt
    assert "slo" in prompt
