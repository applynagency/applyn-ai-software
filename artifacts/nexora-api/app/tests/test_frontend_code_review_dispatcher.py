from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_frontend_code_review_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_code_review") is True


def test_implemented_agents_includes_frontend_code_review():
    assert "frontend_code_review" in IMPLEMENTED_INTERNAL_AGENTS


def test_frontend_code_review_in_implemented_set():
    assert "frontend_code_review" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_v3" in IMPLEMENTED_INTERNAL_AGENTS


def test_dispatcher_frontend_code_review_and_execution_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_v3") is True
    assert dispatcher.is_implemented("frontend_code_review") is True
    assert dispatcher.is_implemented("frontend_execution") is True
