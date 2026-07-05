from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_kubernetes_agent_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("kubernetes_agent") is True


def test_implemented_agents_include_kubernetes_agent():
    assert "kubernetes_agent" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_hyphen_slug_not_implemented_kubernetes():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("kubernetes") is False
