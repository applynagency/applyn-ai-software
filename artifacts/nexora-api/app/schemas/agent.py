from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any
from app.models.agent import AgentType, AgentRunStatus


class AgentRunRequest(BaseModel):
    requirement_id: str
    agent_type: AgentType = AgentType.PRODUCT_OWNER


class UserStory(BaseModel):
    id: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: list[str]
    story_points: int
    priority: str


class Feature(BaseModel):
    id: str
    name: str
    description: str
    user_stories: list[UserStory]


class Epic(BaseModel):
    id: str
    name: str
    description: str
    features: list[Feature]


class SprintPlan(BaseModel):
    sprint_number: int
    duration_weeks: int
    stories: list[str]
    story_points: int
    goals: list[str]


class Risk(BaseModel):
    id: str
    type: str
    description: str
    impact: str
    mitigation: str


class ProductOwnerOutput(BaseModel):
    project_summary: str
    total_story_points: int
    estimated_sprints: int
    epics: list[Epic]
    sprint_plan: list[SprintPlan]
    risks_and_assumptions: list[Risk]
    tech_stack_recommendations: list[str]


class AgentRunResponse(BaseModel):
    id: str
    agent_type: AgentType
    status: AgentRunStatus
    requirement_id: str
    triggered_by: str
    error_message: Optional[str]
    duration_ms: Optional[int]
    tokens_used: Optional[int]
    model_used: Optional[str]
    created_at: datetime
    updated_at: datetime
    output: Optional[ProductOwnerOutput] = None

    model_config = {"from_attributes": True}


class AgentOutputResponse(BaseModel):
    id: str
    agent_run_id: str
    output_type: str
    content: dict[str, Any]
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}
