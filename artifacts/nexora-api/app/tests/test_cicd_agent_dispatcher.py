from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_cicd_agent_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("cicd_agent") is True


def test_implemented_agents_include_cicd_agent():
    assert "cicd_agent" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_hyphen_slug_not_implemented_cicd_agent():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("cicd") is False
