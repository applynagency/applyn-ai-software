from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_deployment_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("deployment") is True


def test_implemented_agents_includes_deployment():
    assert "deployment" in IMPLEMENTED_INTERNAL_AGENTS


def test_deployment_in_implemented_set():
    assert "deployment" in IMPLEMENTED_INTERNAL_AGENTS
    assert "approval" in IMPLEMENTED_INTERNAL_AGENTS


def test_dispatcher_deployment_after_approval():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("fullstack_assembly") is True
    assert dispatcher.is_implemented("approval") is True
    assert dispatcher.is_implemented("deployment") is True


def test_implemented_agents_count_includes_deployment():
    assert len(IMPLEMENTED_INTERNAL_AGENTS) >= 12
