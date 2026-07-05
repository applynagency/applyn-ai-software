from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_qa_approval_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("qa_approval") is True


def test_implemented_agents_include_qa_approval():
    assert "qa_approval" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_qa_approval_hyphen_slug_not_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("qa-approval") is False
