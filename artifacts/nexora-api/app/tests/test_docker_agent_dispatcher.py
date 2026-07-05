from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_docker_agent_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("docker_agent") is True


def test_implemented_agents_include_docker_agent():
    assert "docker_agent" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_hyphen_slug_not_implemented_docker_agent():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("docker-agent") is False
