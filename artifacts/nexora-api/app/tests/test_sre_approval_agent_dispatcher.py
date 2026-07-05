from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_sre_approval_agent_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("sre_approval_agent") is True


def test_implemented_agents_include_sre_approval_agent():
    assert "sre_approval_agent" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_hyphen_slug_not_implemented_sre_approval():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("sre-approval") is False
