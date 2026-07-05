from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_backend_v1_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_v1") is True


def test_implemented_agents_includes_backend_v1():
    assert "backend_v1" in IMPLEMENTED_INTERNAL_AGENTS


def test_backend_v1_follows_backend_architect_in_implemented_list():
    agents = list(IMPLEMENTED_INTERNAL_AGENTS)
    assert "backend_architect" in agents
    assert "backend_v1" in agents


def test_backend_architect_still_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("backend_architect") is True


def test_unimplemented_agent_returns_false():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("developer_v2") is False
