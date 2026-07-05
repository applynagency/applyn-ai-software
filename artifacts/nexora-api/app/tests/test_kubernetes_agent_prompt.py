from app.kubernetes_agent.prompt_builder import KubernetesAgentPromptBuilder


def test_prompt_version_present():
    builder = KubernetesAgentPromptBuilder()
    assert builder.get_prompt_version()


def test_system_prompt_not_empty():
    builder = KubernetesAgentPromptBuilder()
    assert len(builder.get_system_prompt()) > 20


def test_user_prompt_includes_requirement():
    builder = KubernetesAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Build platform",
        infrastructure_architect_output={"infra": "vpc"},
        docker_agent_output={"docker_compose": "services"},
        cicd_agent_output={"github_actions": "ci"},
    )
    assert "Build platform" in prompt


def test_user_prompt_includes_upstream_outputs():
    builder = KubernetesAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Req",
        infrastructure_architect_output={"infra": "vpc-marker"},
        docker_agent_output={"docker_compose": "docker-marker"},
        cicd_agent_output={"github_actions": "cicd-marker"},
    )
    assert "vpc-marker" in prompt
    assert "docker-marker" in prompt
    assert "cicd-marker" in prompt


def test_system_prompt_mentions_constraints():
    builder = KubernetesAgentPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "deployments" in prompt
    assert "ingress" in prompt.lower()
