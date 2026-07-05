"""Pydantic schemas for Custom AI Teams (Sprint 37A)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.ai_team import AITeamStatus

# Reasonable bounds shared by create/update so configuration stays sane.
TEMPERATURE_GE = 0.0
TEMPERATURE_LE = 2.0
MAX_TOKENS_GE = 1
MAX_TOKENS_LE = 200_000


class AITeamAgentCreate(BaseModel):
    team_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=100)
    description: str | None = None
    instructions: str | None = None
    model: str = Field(default="gpt-5", min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=TEMPERATURE_GE, le=TEMPERATURE_LE)
    max_tokens: int = Field(default=1024, ge=MAX_TOKENS_GE, le=MAX_TOKENS_LE)
    is_active: bool = True


class AITeamAgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    instructions: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=100)
    temperature: float | None = Field(default=None, ge=TEMPERATURE_GE, le=TEMPERATURE_LE)
    max_tokens: int | None = Field(default=None, ge=MAX_TOKENS_GE, le=MAX_TOKENS_LE)
    is_active: bool | None = None


class AITeamAgentResponse(BaseModel):
    id: str
    team_id: str
    organization_id: str
    name: str
    role: str
    description: str | None
    instructions: str | None
    model: str
    temperature: float
    max_tokens: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AITeamAgentListResponse(BaseModel):
    items: list[AITeamAgentResponse]
    total: int


class AITeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: AITeamStatus = AITeamStatus.ACTIVE


class AITeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: AITeamStatus | None = None


class AITeamResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None
    status: AITeamStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    agent_count: int = 0
    agents: list[AITeamAgentResponse] = []


class AITeamListResponse(BaseModel):
    items: list[AITeamResponse]
    total: int


# --------------------------------------------------------------- execution
class AITeamAgentExecuteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)


class AITeamAgentExecuteResponse(BaseModel):
    run_id: str
    agent_id: str
    agent_name: str
    response: str | None
    status: str
    execution_time_ms: int
    knowledge_sources: list[str] = []
    memory_sources: list[str] = []


class AITeamAgentRunResponse(BaseModel):
    id: str
    organization_id: str
    agent_id: str
    prompt: str
    response: str | None
    status: str
    execution_time_ms: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AITeamAgentRunListResponse(BaseModel):
    items: list[AITeamAgentRunResponse]
    total: int


# ------------------------------------------------ multi-agent collaboration
class AITeamExecuteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)


class AITeamRunStepResponse(BaseModel):
    id: str
    agent_id: str | None
    agent_name: str
    step_order: int
    prompt: str
    response: str | None
    status: str
    execution_time_ms: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AITeamExecuteStep(BaseModel):
    agent_name: str
    response: str | None


class AITeamExecuteResponse(BaseModel):
    team_id: str
    team_name: str
    run_id: str
    status: str
    execution_time_ms: int
    summary: str | None
    steps: list[AITeamExecuteStep]
    knowledge_sources: list[str] = []
    memory_sources: list[str] = []


# ------------------------------------------------------- knowledge base (37D)
class AITeamDocumentResponse(BaseModel):
    id: str
    organization_id: str
    team_id: str
    filename: str
    content_type: str
    file_size: int
    status: str
    chunk_count: int
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AITeamDocumentListResponse(BaseModel):
    items: list[AITeamDocumentResponse]
    total: int


# ----------------------------------------------------- agent memory (39A)
MEMORY_TYPES = {
    "MEMORY_DECISION",
    "MEMORY_LESSON",
    "MEMORY_CONVERSATION",
    "MEMORY_PROJECT_CONTEXT",
}


class AITeamAgentMemoryCreate(BaseModel):
    memory_type: str = Field(default="MEMORY_DECISION")
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20_000)
    importance_score: int = Field(default=5, ge=1, le=10)
    created_from_run_id: str | None = Field(default=None, max_length=36)

    @field_validator("memory_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of {sorted(MEMORY_TYPES)}")
        return v


class AITeamAgentMemoryUpdate(BaseModel):
    memory_type: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=20_000)
    importance_score: int | None = Field(default=None, ge=1, le=10)

    @field_validator("memory_type")
    @classmethod
    def _validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of {sorted(MEMORY_TYPES)}")
        return v


class AITeamAgentMemoryResponse(BaseModel):
    id: str
    organization_id: str
    agent_id: str
    memory_type: str
    title: str
    content: str
    importance_score: int
    created_from_run_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AITeamAgentMemoryListResponse(BaseModel):
    items: list[AITeamAgentMemoryResponse]
    total: int


# ------------------------------------------------ read-only tool integrations (39B)
TOOL_PROVIDERS = {
    "KUBERNETES",
    "AZURE",
    "AWS",
    "GITHUB",
    "JIRA",
    "POSTGRESQL",
    "PROMETHEUS",
    "GRAFANA",
    "DATADOG",
    "SLACK",
}


class AITeamToolCreate(BaseModel):
    provider: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        up = v.strip().upper()
        if up not in TOOL_PROVIDERS:
            raise ValueError(f"provider must be one of {sorted(TOOL_PROVIDERS)}")
        return up


class AITeamToolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class AITeamToolResponse(BaseModel):
    id: str
    organization_id: str
    provider: str
    name: str
    description: str | None
    is_active: bool
    allowed_actions: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AITeamToolListResponse(BaseModel):
    items: list[AITeamToolResponse]
    total: int


class AITeamToolAssignRequest(BaseModel):
    tool_id: str = Field(min_length=1)


class AITeamToolExecuteRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    action: str = Field(min_length=1, max_length=120)
    payload: dict | None = None


class AITeamToolExecuteResponse(BaseModel):
    run_id: str
    tool_id: str
    agent_id: str
    provider: str
    action: str
    status: str
    response_summary: str | None
    error_message: str | None
    execution_time_ms: int


class AITeamToolRunResponse(BaseModel):
    id: str
    organization_id: str
    agent_id: str | None
    tool_id: str | None
    action: str
    status: str
    request_payload: str | None
    response_summary: str | None
    error_message: str | None
    execution_time_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AITeamToolRunListResponse(BaseModel):
    items: list[AITeamToolRunResponse]
    total: int


# ----------------------------------------- real tool credentials (39C)
class AITeamToolCredentialAttachRequest(BaseModel):
    credential_id: str = Field(min_length=1)


class AITeamToolCredentialResponse(BaseModel):
    id: str
    organization_id: str
    tool_id: str
    credential_id: str
    provider: str
    credential_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AITeamToolConnectionStatusResponse(BaseModel):
    tool_id: str
    provider: str
    attached: bool
    mode: str  # REAL | SIMULATED
    supports_real_connection: bool
    credential_id: str | None = None
    credential_name: str | None = None


class AITeamToolVerifyResponse(BaseModel):
    connected: bool
    provider: str
    details: dict = {}
    error: str | None = None


# --------------------------------------------------- reusable workflows (38A)
class AITeamWorkflowStepInput(BaseModel):
    agent_id: str = Field(min_length=1)
    step_order: int | None = Field(default=None, ge=1)
    custom_instructions: str | None = Field(default=None, max_length=10_000)
    requires_approval: bool = False
    approval_name: str | None = Field(default=None, max_length=255)
    approver_role: str | None = Field(default=None, max_length=120)


class AITeamWorkflowStepResponse(BaseModel):
    id: str
    agent_id: str | None
    agent_name: str
    role: str | None
    is_active: bool
    step_order: int
    custom_instructions: str | None
    requires_approval: bool = False
    approval_name: str | None = None
    approver_role: str | None = None
    created_at: datetime


class AITeamWorkflowCreate(BaseModel):
    team_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    default_prompt: str | None = Field(default=None, max_length=100_000)
    is_active: bool = True
    steps: list[AITeamWorkflowStepInput] = Field(default_factory=list)


class AITeamWorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    default_prompt: str | None = Field(default=None, max_length=100_000)
    is_active: bool | None = None
    # When provided, replaces the full ordered step list.
    steps: list[AITeamWorkflowStepInput] | None = None


class AITeamWorkflowResponse(BaseModel):
    id: str
    organization_id: str
    team_id: str
    team_name: str | None
    name: str
    description: str | None
    default_prompt: str | None
    is_active: bool
    step_count: int
    steps: list[AITeamWorkflowStepResponse] = []
    created_at: datetime
    updated_at: datetime


class AITeamWorkflowListResponse(BaseModel):
    items: list[AITeamWorkflowResponse]
    total: int


class AITeamWorkflowExecuteRequest(BaseModel):
    # Optional: falls back to the workflow's default_prompt when omitted.
    prompt: str | None = Field(default=None, max_length=100_000)


class AITeamWorkflowExecuteResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    run_id: str
    status: str
    execution_source: str = "MANUAL"
    execution_time_ms: int
    summary: str | None
    steps: list[AITeamExecuteStep]
    knowledge_sources: list[str] = []
    memory_sources: list[str] = []


class AITeamWorkflowRunResponse(BaseModel):
    id: str
    organization_id: str
    workflow_id: str
    prompt: str
    summary: str | None
    status: str
    execution_source: str = "MANUAL"
    execution_time_ms: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AITeamWorkflowRunListResponse(BaseModel):
    items: list[AITeamWorkflowRunResponse]
    total: int


# ------------------------------------------------------ human approval gates (38C)
class AITeamWorkflowApprovalResponse(BaseModel):
    id: str
    organization_id: str
    workflow_id: str
    workflow_run_id: str
    step_order: int
    approval_name: str
    approval_description: str | None
    approver_role: str | None
    status: str
    approved_by: str | None
    approved_at: datetime | None
    comments: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AITeamWorkflowApprovalListResponse(BaseModel):
    items: list[AITeamWorkflowApprovalResponse]
    total: int


class AITeamWorkflowApprovalDecisionRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=5000)


# ------------------------------------------------ scheduled workflow runs (38B)
SCHEDULE_TYPES = {"DAILY", "WEEKLY", "MONTHLY", "CUSTOM_CRON"}


class AITeamWorkflowScheduleCreate(BaseModel):
    workflow_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=255)
    schedule_type: str = Field(default="DAILY")
    cron_expression: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="UTC", max_length=64)
    prompt_template: str | None = Field(default=None, max_length=100_000)
    is_active: bool = True


class AITeamWorkflowScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    schedule_type: str | None = None
    cron_expression: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    prompt_template: str | None = Field(default=None, max_length=100_000)
    is_active: bool | None = None


class AITeamWorkflowScheduleResponse(BaseModel):
    id: str
    organization_id: str
    workflow_id: str
    workflow_name: str | None = None
    name: str
    schedule_type: str
    cron_expression: str
    timezone: str
    prompt_template: str | None
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AITeamWorkflowScheduleListResponse(BaseModel):
    items: list[AITeamWorkflowScheduleResponse]
    total: int


class AITeamRunResponse(BaseModel):
    id: str
    organization_id: str
    team_id: str
    prompt: str
    summary: str | None
    status: str
    execution_time_ms: int | None
    error_message: str | None
    created_at: datetime
    steps: list[AITeamRunStepResponse] = []

    model_config = {"from_attributes": True}


class AITeamRunListResponse(BaseModel):
    items: list[AITeamRunResponse]
    total: int
