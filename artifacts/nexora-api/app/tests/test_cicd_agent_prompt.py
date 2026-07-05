
from app.cicd_agent.prompt_builder import CicdAgentPromptBuilder


def test_prompt_version_present():
    builder = CicdAgentPromptBuilder()
    assert builder.get_prompt_version()


def test_system_prompt_not_empty():
    builder = CicdAgentPromptBuilder()
    assert len(builder.get_system_prompt()) > 20


def test_user_prompt_includes_requirement():
    builder = CicdAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Build app",
        docker_agent_output={"docker_compose": "services"},
    )
    assert "Build app" in prompt


def test_user_prompt_includes_docker_output():
    builder = CicdAgentPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Req",
        docker_agent_output={"docker_compose": "services"},
    )
    assert "services" in prompt
