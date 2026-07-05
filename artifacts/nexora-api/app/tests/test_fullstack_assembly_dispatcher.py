from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_fullstack_assembly_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("fullstack_assembly") is True


def test_implemented_agents_includes_fullstack_assembly():
    assert "fullstack_assembly" in IMPLEMENTED_INTERNAL_AGENTS


def test_fullstack_assembly_in_implemented_set():
    assert "fullstack_assembly" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_execution" in IMPLEMENTED_INTERNAL_AGENTS


def test_dispatcher_fullstack_assembly_after_frontend_execution():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_execution") is True
    assert dispatcher.is_implemented("fullstack_assembly") is True
