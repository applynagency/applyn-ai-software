from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_frontend_v1_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_v1") is True


def test_implemented_agents_includes_frontend_v1():
    assert "frontend_v1" in IMPLEMENTED_INTERNAL_AGENTS


def test_frontend_v3_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_v3") is True
