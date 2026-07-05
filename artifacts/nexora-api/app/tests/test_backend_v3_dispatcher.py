from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_backend_v3_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_v3") is True


def test_implemented_agents_includes_backend_v3():
    assert "backend_v3" in IMPLEMENTED_INTERNAL_AGENTS


def test_backend_v3_in_implemented_set():
    assert "backend_v3" in IMPLEMENTED_INTERNAL_AGENTS
    assert "backend_v2" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_code_review" in IMPLEMENTED_INTERNAL_AGENTS


def test_dispatcher_backend_v3_after_backend_v2():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_v2") is True
    assert dispatcher.is_implemented("backend_v3") is True
    assert dispatcher.is_implemented("frontend_code_review") is True
