from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_unit_test_generator_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("unit_test_generator") is True


def test_implemented_agents_include_unit_test_generator():
    assert "unit_test_generator" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_unit_tests_slug_not_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("unit-tests") is False
