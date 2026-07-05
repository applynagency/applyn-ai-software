from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_backend_code_review_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_code_review") is True


def test_implemented_agents_includes_backend_code_review():
    assert "backend_code_review" in IMPLEMENTED_INTERNAL_AGENTS


def test_backend_code_review_in_implemented_set():
    assert "backend_v3" in IMPLEMENTED_INTERNAL_AGENTS
    assert "backend_code_review" in IMPLEMENTED_INTERNAL_AGENTS
