from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_infrastructure_architect_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("infrastructure_architect") is True


def test_implemented_agents_include_infrastructure_architect():
    assert "infrastructure_architect" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_hyphen_slug_not_implemented_infrastructure_architect():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("infrastructure-architect") is False
