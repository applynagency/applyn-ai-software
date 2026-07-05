from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.ai_agent import AIAgentInputType, AIAgentOutputType, AIAgentStatus
from app.models.team import ResponsibilityPriority


class AIAgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    goal: str | None = None
    status: AIAgentStatus = AIAgentStatus.DRAFT
    prompt_template: str | None = None


class AIAgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    goal: str | None = None
    status: AIAgentStatus | None = None
    prompt_template: str | None = None


class AIAgentInputCreate(BaseModel):
    input_name: str = Field(min_length=1, max_length=255)
    input_type: AIAgentInputType = AIAgentInputType.TEXT
    required: bool = True


class AIAgentInputUpdate(BaseModel):
    input_name: str | None = Field(default=None, min_length=1, max_length=255)
    input_type: AIAgentInputType | None = None
    required: bool | None = None


class AIAgentInputResponse(BaseModel):
    id: str
    agent_id: str
    input_name: str
    input_type: AIAgentInputType
    required: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIAgentOutputCreate(BaseModel):
    output_name: str = Field(min_length=1, max_length=255)
    output_type: AIAgentOutputType = AIAgentOutputType.TEXT


class AIAgentOutputUpdate(BaseModel):
    output_name: str | None = Field(default=None, min_length=1, max_length=255)
    output_type: AIAgentOutputType | None = None


class AIAgentOutputResponse(BaseModel):
    id: str
    agent_id: str
    output_name: str
    output_type: AIAgentOutputType
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIAgentResponsibilityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: ResponsibilityPriority = ResponsibilityPriority.MEDIUM


class AIAgentResponsibilityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: ResponsibilityPriority | None = None


class AIAgentResponsibilityResponse(BaseModel):
    id: str
    agent_id: str
    title: str
    description: str | None
    priority: ResponsibilityPriority
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIAgentAssignmentCreate(BaseModel):
    workflow_stage_id: str
    team_id: str | None = None
    execution_order: int = Field(default=1, ge=1)
    is_required: bool = True


class AIAgentAssignmentResponse(BaseModel):
    id: str
    agent_id: str
    workflow_stage_id: str
    workflow_stage_name: str | None = None
    workflow_id: str | None = None
    workflow_name: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    execution_order: int
    is_required: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIAgentResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None
    goal: str | None
    status: AIAgentStatus
    prompt_template: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    input_count: int = 0
    output_count: int = 0
    responsibility_count: int = 0
    assignment_count: int = 0
    inputs: list[AIAgentInputResponse] = []
    outputs: list[AIAgentOutputResponse] = []
    responsibilities: list[AIAgentResponsibilityResponse] = []
    workflow_assignments: list[AIAgentAssignmentResponse] = []

    model_config = {"from_attributes": True}


class AIAgentListResponse(BaseModel):
    items: list[AIAgentResponse]
    total: int


class AIAgentDuplicateResponse(BaseModel):
    agent: AIAgentResponse


class AIAgentAuditEventResponse(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None
    user_id: str | None
    details: dict[str, Any] | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAgentAuditListResponse(BaseModel):
    items: list[AIAgentAuditEventResponse]
    total: int


class StageResolutionTeam(BaseModel):
    team_id: str
    name: str
    team_type: str
    execution_order: int
    is_required: bool
    built_in_agents: list[str] = []


class StageResolutionCustomAgent(BaseModel):
    agent_id: str
    name: str
    goal: str | None
    status: str
    execution_order: int
    is_required: bool
    team_id: str | None = None
    team_name: str | None = None
    prompt_template: str | None = None
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []


class StageAgentResolutionResponse(BaseModel):
    workflow_stage_id: str
    stage_name: str
    workflow_id: str
    workflow_name: str
    teams: list[StageResolutionTeam]
    custom_agents: list[StageResolutionCustomAgent]


class AIAgentTemplatePreview(BaseModel):
    name: str
    goal: str
    input_count: int
    output_count: int


class AIAgentTemplateResponse(BaseModel):
    slug: str
    name: str
    description: str
    category: str
    agent: AIAgentTemplatePreview
    definition: dict[str, Any] | None = None


class AIAgentTemplateListResponse(BaseModel):
    items: list[AIAgentTemplateResponse]
    total: int


class AIAgentTemplateApplyRequest(BaseModel):
    template_slug: str


class AIAgentTemplateApplyResponse(BaseModel):
    template_slug: str
    agent: AIAgentResponse
