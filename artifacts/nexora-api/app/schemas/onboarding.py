"""Sprint 47C - Guided Setup Wizard schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    # If an in-progress session exists it is resumed unless force_new is set.
    force_new: bool = False
    organization_name: str | None = None


class StepRequest(BaseModel):
    step: str
    data: dict = Field(default_factory=dict)
    completed: bool = True


class StepInfo(BaseModel):
    key: str
    order: int
    title: str
    description: str
    completed: bool = False
    auto_detected: bool = False


class Recommendation(BaseModel):
    step: str
    title: str
    action: str


class OnboardingResponse(BaseModel):
    id: str
    organization_id: str
    status: str
    current_step: str
    progress_percent: int
    steps: list[StepInfo] = []
    completed_steps: list[str] = []
    missing_steps: list[str] = []
    recommendations: list[Recommendation] = []
    summary: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OnboardingCompleteResponse(OnboardingResponse):
    # Completing onboarding auto-provisions the org's default SRE team so incident
    # investigation works immediately, and surfaces the next-best action.
    default_team: dict | None = None
    next_actions: list[dict] = []


class SampleIncidentResponse(BaseModel):
    scenario: str
    scenario_id: str
    incident_id: str | None = None
    incident_ids: list[str] = []
    run: dict = Field(default_factory=dict)
    next_actions: list[dict] = []
