from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.workflow import StageType, WorkflowRuleType, WorkflowStatus


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: WorkflowStatus = WorkflowStatus.DRAFT
    is_default: bool = False


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: WorkflowStatus | None = None
    is_default: bool | None = None


class WorkflowStageTeamResponse(BaseModel):
    id: str
    workflow_stage_id: str
    team_id: str
    team_name: str | None = None
    execution_order: int
    is_required: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowStageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sequence: int = Field(ge=1)
    stage_type: StageType = StageType.CUSTOM
    approval_required: bool = False


class WorkflowStageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    sequence: int | None = Field(default=None, ge=1)
    stage_type: StageType | None = None
    approval_required: bool | None = None


class WorkflowStageResponse(BaseModel):
    id: str
    workflow_id: str
    name: str
    description: str | None
    sequence: int
    stage_type: StageType
    approval_required: bool
    created_at: datetime
    updated_at: datetime
    team_count: int = 0
    team_assignments: list[WorkflowStageTeamResponse] = []

    model_config = {"from_attributes": True}


class WorkflowRuleCreate(BaseModel):
    rule_type: WorkflowRuleType
    configuration_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowRuleResponse(BaseModel):
    id: str
    workflow_id: str
    rule_type: WorkflowRuleType
    configuration_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None
    status: WorkflowStatus
    is_default: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    stage_count: int = 0
    team_assignment_count: int = 0
    rule_count: int = 0
    stages: list[WorkflowStageResponse] = []
    rules: list[WorkflowRuleResponse] = []

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int


class WorkflowDuplicateResponse(BaseModel):
    workflow: WorkflowResponse


class WorkflowStageTeamAssign(BaseModel):
    team_id: str
    execution_order: int = Field(default=1, ge=1)
    is_required: bool = True


class ExecutionPlanTeam(BaseModel):
    team_id: str
    name: str
    team_type: str
    execution_order: int
    is_required: bool
    agents: list[str] = []


class ExecutionPlanStage(BaseModel):
    stage_id: str
    name: str
    sequence: int
    stage_type: str
    approval_required: bool
    teams: list[str]
    team_details: list[ExecutionPlanTeam] = []


class ExecutionPlanResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    status: str
    stages: list[ExecutionPlanStage]
    rules: list[dict[str, Any]] = []


class WorkflowAuditEventResponse(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None
    user_id: str | None
    details: dict[str, Any] | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowAuditListResponse(BaseModel):
    items: list[WorkflowAuditEventResponse]
    total: int


class WorkflowTemplateStagePreview(BaseModel):
    name: str
    sequence: int
    stage_type: StageType
    team_count: int


class WorkflowTemplateResponse(BaseModel):
    slug: str
    name: str
    description: str
    industry: str
    stage_count: int
    stages: list[WorkflowTemplateStagePreview]
    definition: dict[str, Any] | None = None


class WorkflowTemplateListResponse(BaseModel):
    items: list[WorkflowTemplateResponse]
    total: int


class WorkflowTemplateApplyRequest(BaseModel):
    template_slug: str


class WorkflowTemplateApplyResponse(BaseModel):
    template_slug: str
    workflow: WorkflowResponse
