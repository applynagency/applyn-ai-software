from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.team import ResponsibilityPriority, TeamStatus, TeamType


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    team_type: TeamType = TeamType.CUSTOM
    status: TeamStatus = TeamStatus.DRAFT


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    team_type: TeamType | None = None
    status: TeamStatus | None = None


class TeamAgentMappingResponse(BaseModel):
    id: str
    team_id: str
    internal_agent: str
    execution_order: int
    is_required: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamResponsibilityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: ResponsibilityPriority = ResponsibilityPriority.MEDIUM


class TeamResponsibilityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: ResponsibilityPriority | None = None


class TeamResponsibilityResponse(BaseModel):
    id: str
    team_id: str
    title: str
    description: str | None
    priority: ResponsibilityPriority
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None
    team_type: TeamType
    status: TeamStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    responsibility_count: int = 0
    workflow_count: int = 0
    agent_count: int = 0
    responsibilities: list[TeamResponsibilityResponse] = []
    agent_mappings: list[TeamAgentMappingResponse] = []

    model_config = {"from_attributes": True}


class TeamListResponse(BaseModel):
    items: list[TeamResponse]
    total: int


class TeamDuplicateResponse(BaseModel):
    team: TeamResponse


class TeamAuditEventResponse(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None
    user_id: str | None
    details: dict[str, Any] | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamAuditListResponse(BaseModel):
    items: list[TeamAuditEventResponse]
    total: int


class TeamTemplateTeamPreview(BaseModel):
    name: str
    description: str
    team_type: TeamType
    responsibility_count: int


class TeamTemplateResponse(BaseModel):
    slug: str
    name: str
    description: str
    industry: str
    team_count: int
    teams: list[TeamTemplateTeamPreview]
    definition: dict[str, Any] | None = None


class TeamTemplateListResponse(BaseModel):
    items: list[TeamTemplateResponse]
    total: int


class TeamTemplateApplyRequest(BaseModel):
    template_slug: str


class TeamTemplateApplyResponse(BaseModel):
    template_slug: str
    teams_created: int
    items: list[TeamResponse]
