from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_backend_execution_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_execution") is True


def test_implemented_agents_includes_backend_execution():
    assert "backend_execution" in IMPLEMENTED_INTERNAL_AGENTS


def test_backend_execution_in_implemented_set():
    assert "backend_execution" in IMPLEMENTED_INTERNAL_AGENTS
    assert "backend_code_review" in IMPLEMENTED_INTERNAL_AGENTS


def test_dispatcher_backend_execution_after_backend_code_review():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_code_review") is True
    assert dispatcher.is_implemented("backend_execution") is True
