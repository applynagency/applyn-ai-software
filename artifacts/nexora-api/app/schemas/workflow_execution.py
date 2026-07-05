from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.workflow_execution import ExecutionAgentKind, ExecutionStatus


class WorkflowExecuteRequest(BaseModel):
    project_id: str
    requirement_id: str


class ExecutionPlanAgentItem(BaseModel):
    agent_kind: Literal["internal", "custom"]
    internal_agent: str | None = None
    custom_agent_id: str | None = None
    name: str
    team_id: str | None = None
    team_name: str | None = None
    execution_order: int
    is_required: bool = True
    is_implemented: bool = False
    prompt_template: str | None = None


class ExecutionPlanStageItem(BaseModel):
    stage_id: str
    name: str
    sequence: int
    stage_type: str
    approval_required: bool
    agents: list[ExecutionPlanAgentItem] = []


class FullExecutionPlan(BaseModel):
    organization_id: str
    workflow_id: str
    workflow_name: str
    project_id: str
    requirement_id: str
    stages: list[ExecutionPlanStageItem]
    rules: list[dict[str, Any]] = []


class WorkflowExecutionAgentResponse(BaseModel):
    id: str
    workflow_execution_id: str
    workflow_execution_stage_id: str
    agent_kind: ExecutionAgentKind
    internal_agent: str | None
    custom_agent_id: str | None
    team_id: str | None
    agent_name: str
    team_name: str | None
    execution_order: int
    is_required: bool
    status: ExecutionStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    tokens_used: int | None
    output_json: dict[str, Any] | None
    error_message: str | None
    agent_run_id: str | None
    log_messages: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowExecutionStageResponse(BaseModel):
    id: str
    workflow_execution_id: str
    workflow_stage_id: str | None
    name: str
    sequence: int
    stage_type: str
    status: ExecutionStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    agents: list[WorkflowExecutionAgentResponse] = []

    model_config = {"from_attributes": True}


class WorkflowExecutionResponse(BaseModel):
    id: str
    organization_id: str
    workflow_id: str
    project_id: str
    requirement_id: str
    status: ExecutionStatus
    started_by: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    execution_plan_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    stage_count: int = 0
    agent_count: int = 0
    stages: list[WorkflowExecutionStageResponse] = []

    model_config = {"from_attributes": True}


class WorkflowExecutionListResponse(BaseModel):
    items: list[WorkflowExecutionResponse]
    total: int


class WorkflowExecutionStatusResponse(BaseModel):
    id: str
    status: ExecutionStatus
    workflow_id: str
    requirement_id: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    stages: list[WorkflowExecutionStageResponse] = []

    model_config = {"from_attributes": True}


class WorkflowExecutionAuditEventResponse(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None
    user_id: str | None
    details: dict[str, Any] | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowExecutionAuditListResponse(BaseModel):
    items: list[WorkflowExecutionAuditEventResponse]
    total: int
