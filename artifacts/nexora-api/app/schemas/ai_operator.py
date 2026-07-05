"""Pydantic schemas for AI Platform Operator API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    name: str
    mode: str = "APPROVAL_REQUIRED"
    rules: dict = Field(default_factory=dict)


class PolicyView(BaseModel):
    id: str
    name: str
    mode: str
    rules: dict
    is_active: bool

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    metric: str
    title: str
    target_value: float
    unit: str = "%"


class GoalView(BaseModel):
    id: str
    metric: str
    title: str
    target_value: float
    unit: str
    current_value: float | None
    progress_percent: float | None
    is_active: bool
    achieved_at: datetime | None

    model_config = {"from_attributes": True}


class RecommendationView(BaseModel):
    id: str
    kind: str
    title: str
    status: str
    confidence: float
    impact: str
    risk: str
    evidence: list
    referenced_resources: list
    rollback_plan: str | None
    estimated_savings: float | None
    reasoning: str | None
    simulation_id: str | None
    environment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SimulationView(BaseModel):
    id: str
    recommendation_id: str | None
    kind: str
    result: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ProposalView(BaseModel):
    id: str
    recommendation_id: str
    status: str
    action_payload: dict
    execution_result: dict | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TimelineView(BaseModel):
    id: str
    kind: str
    title: str
    detail: dict
    recommendation_id: str | None
    proposal_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LearningView(BaseModel):
    id: str
    source: str
    outcome: str
    lesson: str
    record_metadata: dict
    recommendation_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardView(BaseModel):
    mode: str
    pending_recommendations: int
    pending_proposals: int
    active_goals: int
    total_savings_estimate: float
    recent_findings: list
    predictions: list
    goal_progress: list


class ExecutiveBriefingView(BaseModel):
    id: str
    period_start: datetime
    period_end: datetime
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class SavingsView(BaseModel):
    total_estimated_savings: float
    recommendations_with_savings: int
    top_opportunities: list


class AnalyzeRequest(BaseModel):
    trigger: str | None = None


class AIContextView(BaseModel):
    suggested_questions: list[str]
    recent_recommendations: list
    active_policies: int
    mode: str
