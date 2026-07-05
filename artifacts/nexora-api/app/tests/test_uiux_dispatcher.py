from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


def test_dispatcher_knows_uiux_designer_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("uiux_designer") is True


def test_implemented_agents_includes_uiux_designer():
    assert "uiux_designer" in IMPLEMENTED_INTERNAL_AGENTS


def test_legacy_ui_ux_designer_slug_not_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("ui_ux_designer") is False
