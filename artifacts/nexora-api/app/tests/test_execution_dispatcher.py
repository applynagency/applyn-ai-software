from app.workflows.dispatcher import AgentDispatcher


def test_dispatcher_knows_product_owner_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("product_owner") is True


def test_dispatcher_frontend_v2_v3_code_review_and_execution_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_v2") is True
    assert dispatcher.is_implemented("frontend_v3") is True
    assert dispatcher.is_implemented("frontend_code_review") is True
    assert dispatcher.is_implemented("frontend_execution") is True
    assert dispatcher.is_implemented("developer_v1") is False
    assert dispatcher.is_implemented("ui_ux_designer") is False


def test_implemented_agents_set():
    from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS

    assert "product_owner" in IMPLEMENTED_INTERNAL_AGENTS
    assert "business_analyst" in IMPLEMENTED_INTERNAL_AGENTS
    assert "uiux_designer" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_architect" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_v1" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_v2" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_v3" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_code_review" in IMPLEMENTED_INTERNAL_AGENTS
    assert "frontend_execution" in IMPLEMENTED_INTERNAL_AGENTS


def test_dispatcher_knows_business_analyst_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("business_analyst") is True


def test_dispatcher_knows_uiux_designer_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("uiux_designer") is True


def test_dispatcher_knows_frontend_architect_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_architect") is True


def test_dispatcher_knows_frontend_v1_implemented():
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented("frontend_v1") is True


def test_execution_status_enum_values():
    from app.models.workflow_execution import ExecutionStatus

    assert ExecutionStatus.PENDING.value == "PENDING"
    assert ExecutionStatus.RUNNING.value == "RUNNING"
    assert ExecutionStatus.COMPLETED.value == "COMPLETED"
    assert ExecutionStatus.FAILED.value == "FAILED"
    assert ExecutionStatus.SKIPPED.value == "SKIPPED"
    assert ExecutionStatus.WAITING_FOR_APPROVAL.value == "WAITING_FOR_APPROVAL"


def test_execution_agent_kind_enum():
    from app.models.workflow_execution import ExecutionAgentKind

    assert ExecutionAgentKind.INTERNAL.value == "INTERNAL"
    assert ExecutionAgentKind.CUSTOM.value == "CUSTOM"
