from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_security_test_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("security_test") is True


def test_implemented_agents_include_security_test():
    assert "security_test" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_security_test_hyphen_slug_not_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("security-test") is False
