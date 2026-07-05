from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_approval_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("approval") is True


def test_implemented_agents_includes_approval():
    assert "approval" in IMPLEMENTED_INTERNAL_AGENTS


def test_approval_in_implemented_set():
    assert "approval" in IMPLEMENTED_INTERNAL_AGENTS
    assert "fullstack_assembly" in IMPLEMENTED_INTERNAL_AGENTS


def test_dispatcher_approval_after_fullstack_assembly():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("fullstack_assembly") is True
    assert dispatcher.is_implemented("approval") is True
