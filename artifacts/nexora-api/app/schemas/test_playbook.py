"""Sprint 51B - Test Playbook Engine schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ steps
class StepCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    action: str | None = None
    expected_result: str | None = None
    validation_criteria: str | None = None
    order_index: int | None = None


class StepView(BaseModel):
    id: str
    order_index: int
    title: str
    action: str | None = None
    expected_result: str | None = None
    validation_criteria: str | None = None

    model_config = {"from_attributes": True}


# ------------------------------------------------------------- playbooks
class PlaybookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: str
    description: str | None = None
    preconditions: str | None = None
    validation_criteria: str | None = None
    tags: list[str] = []
    steps: list[StepCreate] = []


class PlaybookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = None
    description: str | None = None
    preconditions: str | None = None
    validation_criteria: str | None = None
    tags: list[str] | None = None
    steps: list[StepCreate] | None = None


class PlaybookSummary(BaseModel):
    id: str
    name: str
    category: str
    description: str | None = None
    step_count: int = 0
    run_count: int = 0
    last_run_status: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlaybookDetail(BaseModel):
    id: str
    organization_id: str
    name: str
    category: str
    description: str | None = None
    preconditions: str | None = None
    validation_criteria: str | None = None
    tags: list[str] = []
    is_system: bool = False
    steps: list[StepView] = []
    run_count: int = 0
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------- runs
class StepResultInput(BaseModel):
    step_id: str
    status: str  # PASSED | FAILED | SKIPPED
    actual_result: str | None = None
    notes: str | None = None


class ExecuteRequest(BaseModel):
    step_results: list[StepResultInput] = []
    notes: str | None = None


class StepResultView(BaseModel):
    step_id: str
    title: str
    status: str
    expected_result: str | None = None
    actual_result: str | None = None
    notes: str | None = None


class RunView(BaseModel):
    id: str
    playbook_id: str
    organization_id: str
    status: str
    total_steps: int
    passed_steps: int
    failed_steps: int
    skipped_steps: int
    pass_rate: int
    results: list[StepResultView] = []
    summary: str | None = None
    notes: str | None = None
    executed_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
