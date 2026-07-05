from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_frontend_architect_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_architect") is True


def test_implemented_agents_includes_frontend_architect():
    assert "frontend_architect" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_frontend_architect_hyphen_slug_not_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend-architect") is False
