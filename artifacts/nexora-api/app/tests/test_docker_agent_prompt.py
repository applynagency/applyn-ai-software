
from app.docker_agent.prompt_builder import DockerAgentPromptBuilder


def test_prompt_version_present():
    builder = DockerAgentPromptBuilder()
    assert builder.get_prompt_version()


def test_system_prompt_not_empty():
    builder = DockerAgentPromptBuilder()
    assert len(builder.get_system_prompt()) > 20


def test_user_prompt_includes_requirement():
    builder = DockerAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Build app",
        infrastructure_architect_output={"cloud_architecture": "azure"},
    )
    assert "Build app" in prompt


def test_user_prompt_includes_infrastructure_output():
    builder = DockerAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Req",
        infrastructure_architect_output={"cloud_architecture": "azure"},
    )
    assert "azure" in prompt
