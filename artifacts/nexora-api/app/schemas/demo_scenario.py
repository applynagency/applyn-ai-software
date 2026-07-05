"""Sprint 52C.1 — Demo Scenario Engine schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

class FlowStep(BaseModel):
    step: int
    name: str
    system: str
    description: str


class ScenarioView(BaseModel):
    id: str
    organization_id: str
    scenario_type: str
    name: str
    description: str | None
    template_key: str | None
    status: str
    run_count: int
    last_run_id: str | None
    is_builtin: bool
    flow_steps: list[dict[str, Any]]
    created_at: datetime


class ScenarioListResponse(BaseModel):
    items: list[ScenarioView]
    total: int


class ScenarioRunRequest(BaseModel):
    """Optional payload for POST run/replay.  (run_id only for replay)"""
    run_id: str | None = Field(default=None, description="Specific run ID to replay from.")


class StepLogEntry(BaseModel):
    step: int
    status: str
    summary: str
    timestamp: str


class ScenarioRunView(BaseModel):
    id: str
    organization_id: str
    scenario_id: str
    is_replay: bool
    replayed_from_id: str | None
    status: str
    total_steps: int
    completed_steps: int
    duration_seconds: float | None
    incident_ids: list[str]
    alert_ids: list[str]
    generated_events: list[dict[str, Any]]
    step_log: list[dict[str, Any]]
    error_message: str | None
    created_at: datetime


class ScenarioRunListResponse(BaseModel):
    items: list[ScenarioRunView]
    total: int


# ---------------------------------------------------------------------------
# Walkthroughs
# ---------------------------------------------------------------------------

class WalkthroughStep(BaseModel):
    step: int
    title: str
    module: str
    description: str
    expected_result: str
    next_action: str
    screenshot_filename: str
    screenshot_url: str
    screenshot_caption: str
    callout: str


class WalkthroughResponse(BaseModel):
    org_id: str
    scenario_type: str | None
    total_steps: int
    steps: list[dict[str, Any]]
    completion_message: str


class ScreenshotAsset(BaseModel):
    filename: str
    module: str
    category: str
    caption: str


class ScreenshotManifest(BaseModel):
    base_url: str
    total: int
    assets: list[ScreenshotAsset]


# ---------------------------------------------------------------------------
# Sales Demo Mode
# ---------------------------------------------------------------------------

class ValueCallout(BaseModel):
    title: str
    metric: str
    description: str
    module: str


class SalesDashboardResponse(BaseModel):
    mode: str
    user_id: str
    presentation_mode: bool
    demo_organizations: list[dict[str, Any]]
    total_demo_orgs: int
    scenarios: list[dict[str, Any]]
    total_scenarios: int
    completed_runs: int
    total_assets: int
    walkthrough_steps: list[dict[str, Any]]
    total_walkthrough_steps: int
    value_callouts: list[dict[str, Any]]
    screenshot_manifest: dict[str, Any]
    navigation: list[dict[str, Any]]
    simulated_credentials_note: str
