from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_integration_test_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("integration_test") is True


def test_implemented_agents_include_integration_test():
    assert "integration_test" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_integration_test_hyphen_slug_not_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("integration-test") is False
