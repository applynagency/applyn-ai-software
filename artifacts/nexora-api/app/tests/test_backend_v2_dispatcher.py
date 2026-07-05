from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_backend_v2_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_v2") is True


def test_implemented_agents_includes_backend_v2():
    assert "backend_v2" in IMPLEMENTED_INTERNAL_AGENTS


def test_backend_v2_follows_backend_v1_in_implemented_list():
    agents = list(IMPLEMENTED_INTERNAL_AGENTS)
    assert agents.index("backend_v1") < agents.index("backend_v2")


def test_backend_v1_still_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_v1") is True


def test_backend_v2_precedes_uiux_designer_in_implemented_list():
    agents = list(IMPLEMENTED_INTERNAL_AGENTS)
    assert agents.index("backend_v2") < agents.index("uiux_designer")
