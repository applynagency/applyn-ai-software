from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_performance_test_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("performance_test") is True


def test_implemented_agents_include_performance_test():
    assert "performance_test" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_performance_test_hyphen_slug_not_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("performance-test") is False
