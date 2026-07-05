"""Sprint 40A — Incident Investigation Engine schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class IncidentInvestigateRequest(BaseModel):
    # Sprint 54B.1 — optional. When omitted, the organization's default team
    # (the auto-provisioned "SRE Team") is used, removing a hidden prerequisite.
    team_id: str | None = Field(default=None, min_length=1)
    # Optional: investigate as a specific agent. Defaults to the team's first
    # active agent when omitted.
    agent_id: str | None = None
    title: str | None = Field(default=None, max_length=255)
    prompt: str = Field(min_length=1, max_length=5000)
    # Optional read-only scoping passed to each tool (e.g. namespace, owner,
    # repo, query). Secret-like keys are redacted before persistence.
    context: dict | None = None


class IncidentStepResponse(BaseModel):
    id: str
    investigation_id: str
    step_order: int
    tool_provider: str
    action: str
    status: str
    result_summary: str | None
    execution_time_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: str
    organization_id: str
    team_id: str | None
    agent_id: str | None
    title: str
    prompt: str
    status: str
    summary: str | None
    root_cause: str | None
    recommendations: str | None
    # Sprint 40B — correlation results.
    confidence_score: int | None = None
    suspected_trigger: str | None = None
    suspected_provider: str | None = None
    # Sprint 42A — provenance (MANUAL vs MONITORING) + alert severity.
    source: str = "MANUAL"
    severity: str | None = None
    # Sprint 58A.4 — production incident lifecycle.
    lifecycle_status: str = "OPEN"
    assignee_id: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentDetailResponse(IncidentResponse):
    findings: list[str] = []
    steps: list[IncidentStepResponse] = []


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    total: int


class IncidentTimelineEventResponse(BaseModel):
    """Sprint 40B — a single normalized event on the incident timeline."""

    id: str
    investigation_id: str
    provider: str
    event_type: str
    event_timestamp: datetime
    title: str
    description: str | None = None
    severity: str
    metadata: dict | None = Field(default=None, validation_alias="event_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class IncidentTriggerAnalysis(BaseModel):
    """Sprint 40B — most likely initiating change and the correlation gaps."""

    suspected_trigger: str | None = None
    suspected_provider: str | None = None
    confidence_score: int = 0
    reason: str | None = None
    first_change_at: datetime | None = None
    first_failure_at: datetime | None = None
    first_alert_at: datetime | None = None
    first_degradation_at: datetime | None = None
    minutes_between_change_and_failure: int | None = None
    minutes_between_failure_and_alert: int | None = None
    impacted_systems: list[str] = []


class IncidentTimelineResponse(BaseModel):
    investigation_id: str
    status: str
    steps: list[IncidentStepResponse]
    # Sprint 40B additions.
    timeline: list[IncidentTimelineEventResponse] = []
    trigger_analysis: IncidentTriggerAnalysis | None = None
    confidence_score: int | None = None


class DeploymentChangeEventResponse(BaseModel):
    """Sprint 40C — a single normalized deployment/change event."""

    id: str
    investigation_id: str
    provider: str
    change_type: str
    change_timestamp: datetime
    actor: str | None = None
    title: str
    description: str | None = None
    version: str | None = None
    metadata: dict | None = Field(default=None, validation_alias="event_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SuspectedChange(BaseModel):
    """Sprint 40C — the change most likely to have triggered the incident."""

    provider: str | None = None
    change_type: str | None = None
    title: str | None = None
    actor: str | None = None
    version: str | None = None
    commit: str | None = None
    change_timestamp: datetime | None = None
    minutes_to_failure: int | None = None
    confidence_score: int = 0
    reason: str | None = None


class IncidentChangesResponse(BaseModel):
    """Sprint 40C — response for GET /v1/incidents/{id}/changes."""

    investigation_id: str
    changes: list[DeploymentChangeEventResponse] = []
    suspected_change: SuspectedChange | None = None
    confidence_score: int | None = None
    latest_commit: str | None = None
    latest_merge: str | None = None
    latest_release: str | None = None


class IncidentRecommendationResponse(BaseModel):
    """Sprint 41A — a single ranked remediation recommendation (advisory only)."""

    id: str
    investigation_id: str
    recommendation_type: str
    title: str
    description: str | None = None
    risk_level: str
    confidence_score: int
    estimated_recovery_minutes: int | None = None
    recommendation_order: int
    metadata: dict | None = Field(default=None, validation_alias="event_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class IncidentRecommendationsResponse(BaseModel):
    """Sprint 41A — response for GET /v1/incidents/{id}/recommendations."""

    investigation_id: str
    recommendations: list[IncidentRecommendationResponse] = []


class RemediationActionResponse(BaseModel):
    """Sprint 41B — an approval-gated remediation action."""

    id: str
    organization_id: str
    investigation_id: str
    recommendation_id: str | None = None
    action_type: str
    provider: str
    title: str
    description: str | None = None
    risk_level: str
    status: str
    credential_id: str | None = None
    environment: str | None = None
    namespace: str | None = None
    application: str | None = None
    bound: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    execution_result: str | None = None
    error_message: str | None = None
    metadata: dict | None = Field(default=None, validation_alias="action_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}

    @model_validator(mode="after")
    def _set_bound(self):
        # An action is "bound" once it has a credential + deploy target.
        # Kubernetes execution also requires a namespace (see RemediationActionService._is_executable).
        if (self.provider or "").upper() == "KUBERNETES":
            self.bound = bool(self.credential_id and self.application and self.namespace)
        else:
            self.bound = bool(self.credential_id and self.application)
        return self


class RemediationActionListResponse(BaseModel):
    investigation_id: str
    actions: list[RemediationActionResponse] = []


class RemediationApprovalResponse(BaseModel):
    """Sprint 41B — a recorded approval/rejection decision."""

    id: str
    action_id: str
    approver_user_id: str | None = None
    status: str
    comments: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RemediationApprovalListResponse(BaseModel):
    action_id: str
    approvals: list[RemediationApprovalResponse] = []


class RemediationDecisionRequest(BaseModel):
    """Sprint 41B — body for approve/reject (comments optional)."""

    comments: str | None = Field(default=None, max_length=2000)


class RemediationBindRequest(BaseModel):
    """Sprint 41C — bind an action to real target infrastructure before approval.

    Only references an encrypted credential (by id) plus non-secret target
    coordinates. Never carries secret values.
    """

    credential_id: str
    environment: str | None = Field(default=None, max_length=80)
    namespace: str | None = Field(default=None, max_length=160)
    application: str | None = Field(default=None, max_length=200)
    target_config: dict | None = None


class IncidentEvidenceResponse(BaseModel):
    """Operational evidence bundle for incident triage (logs, metrics, CI context)."""

    investigation_id: str
    service: str | None = None
    suspected_provider: str | None = None
    linked_alerts: int = 0
    logs: dict | None = None
    metrics: list[dict] = []
    build_context: dict | None = None


class NotificationChannelsResponse(BaseModel):
    slack_webhook_configured: bool = False
    teams_webhook_configured: bool = False
    pagerduty_routing_configured: bool = False
    slack_webhook_preview: str | None = None
    teams_webhook_preview: str | None = None
    default_channels: list[str] = ["slack", "email"]
    env_fallback: dict = {}


class NotificationChannelsUpdateRequest(BaseModel):
    slack_webhook_url: str | None = None
    teams_webhook_url: str | None = None
    pagerduty_routing_key: str | None = None
    default_channels: list[str] | None = None
    clear_slack: bool = False
    clear_teams: bool = False
    clear_pagerduty: bool = False
