"""Sprint 51D - Interactive Product Tour schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StepView(BaseModel):
    id: str
    order_index: int
    title: str
    body: str | None = None
    target_route: str | None = None
    target_selector: str | None = None
    module: str | None = None
    cta_label: str | None = None

    model_config = {"from_attributes": True}


class ProgressView(BaseModel):
    id: str
    tour_id: str
    user_id: str
    status: str
    current_step_index: int
    completed_step_ids: list[str] = []
    progress_percent: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    last_activity_at: str | None = None

    model_config = {"from_attributes": True}


class TourSummary(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    audience: str
    is_first_login: bool = False
    estimated_minutes: int | None = None
    step_count: int = 0
    progress: ProgressView | None = None


class TourDetail(BaseModel):
    id: str
    organization_id: str
    key: str
    name: str
    description: str | None = None
    audience: str
    is_first_login: bool = False
    estimated_minutes: int | None = None
    steps: list[StepView] = []
    progress: ProgressView | None = None


class StartRequest(BaseModel):
    tour_id: str | None = None
    tour_key: str | None = None
    restart: bool = False


class StepRequest(BaseModel):
    step_id: str | None = None
    step_index: int | None = Field(default=None, ge=0)


class StartResponse(BaseModel):
    tour: TourDetail
    progress: ProgressView


class ContextualHelpResponse(BaseModel):
    module: str | None = None
    route: str | None = None
    steps: list[StepView] = []
