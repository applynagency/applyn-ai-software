"""Customer pilot portal API schemas (Sprint 67B)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerPilotOverviewView(BaseModel):
    portal_visible: bool
    enrollment_id: str | None = None
    execution_status: str | None = None
    current_stage: str | None = None
    scope: dict = Field(default_factory=dict)
    safety: dict = Field(default_factory=dict)
    operation_summary: dict | None = None
    approval_status: str | None = None
    execution_label: str | None = None
    verification_status: str | None = None
    closeout_status: str | None = None
    integration_badges: list[dict] = Field(default_factory=list)


class CustomerPilotTimelineView(BaseModel):
    events: list[dict] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    stage_summary: list[dict] = Field(default_factory=list)
    current_stage: str | None = None


class CustomerTimelineExportView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    json_payload: dict = Field(serialization_alias="json")
    markdown: str
    html: str
    pdf_base64: str | None = None
    redacted: bool = True
    export_blocked: bool = False
    block_reason: str | None = None


class CustomerCommunicationView(BaseModel):
    id: str
    category: str
    status: str
    title: str
    body: str
    deep_link: str | None = None
    operation_id: str | None = None
    sent_at: str | None = None
    acknowledgements: list[dict] = Field(default_factory=list)
    recipient_count: int = 0
    created_at: str | None = None


class CustomerCommunicationCommentPayload(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


class CustomerNotificationPreferencesView(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = False
    approval_reminders_enabled: bool = True
    evidence_ready_enabled: bool = True
    closeout_notifications_enabled: bool = True
    timezone: str = "UTC"


class CustomerNotificationPreferencesUpdate(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    approval_reminders_enabled: bool | None = None
    evidence_ready_enabled: bool | None = None
    closeout_notifications_enabled: bool | None = None
    timezone: str | None = None


class PilotCommunicationDraftRequest(BaseModel):
    category: str
    template_key: str | None = None
    operation_id: str | None = None
    recipient_user_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    body: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)


class PilotCommunicationSendView(BaseModel):
    communication: CustomerCommunicationView
    blockers: list[str] = Field(default_factory=list)


class CustomerPilotOperationView(BaseModel):
    id: str
    action: str
    resource_name: str
    status: str
    environment: dict = Field(default_factory=dict)
    scope: dict = Field(default_factory=dict)
    rollback_plan: str | None = None
    preflight_summary: dict = Field(default_factory=dict)
    before_state: dict = Field(default_factory=dict)
    payload_hash: str | None = None
    approval_id: str | None = None
    verification_status: str | None = None
    operator_handoff_status: str | None = None


class CustomerApprovalPackageView(BaseModel):
    immutable: bool = True
    package: dict = Field(default_factory=dict)
    markdown: str | None = None
    html: str | None = None
    payload_hash: str
    rollback_plan_hash: str
    expires_at: str | None = None


class CustomerApprovalDecideRequest(BaseModel):
    approver_name: str
    approver_email: str
    approve: bool
    rationale: str
    payload_hash_acknowledged: str
    rollback_plan_acknowledged: bool = True


class CustomerApprovalDecideView(BaseModel):
    approval_id: str
    operation_id: str
    status: str
    decision_rationale: str
    operator_handoff_status: str | None = None


class CustomerExecutionStatusView(BaseModel):
    operation_id: str
    status: str
    verification_status: str | None = None
    source_mode: str | None = None
    gates: dict = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    ready_for_operator_confirmation: bool = False


class CustomerVerificationView(BaseModel):
    operation_id: str
    verification_status: str
    summary: dict = Field(default_factory=dict)
    kubernetes_summary: dict | None = None
    prometheus_summary: dict | None = None
    gaps: list[str] = Field(default_factory=list)


class CustomerEvidenceView(BaseModel):
    operation_id: str | None = None
    evidence: dict = Field(default_factory=dict)
    audit_timeline: list[dict] = Field(default_factory=list)
    redacted: bool = True


class CustomerEvidenceExportView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    json_payload: dict = Field(serialization_alias="json")
    markdown: str
    html: str
    pdf_base64: str | None = None
    redacted: bool = True
    export_blocked: bool = False
    block_reason: str | None = None


class CustomerCloseoutView(BaseModel):
    status: str
    eligible: bool
    blockers: list[str] = Field(default_factory=list)
    request: dict | None = None


class CustomerCloseoutRequestPayload(BaseModel):
    signoff_contact: str
    customer_comments: str | None = None
    outcome_rating: int | None = Field(default=None, ge=1, le=5)
    follow_up_requested: bool = False
    documented_no_operation: bool = False


class CustomerNotificationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    category: str
    priority: str
    action_url: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class OperatorHandoffView(BaseModel):
    operation_id: str
    handoff_status: str
    customer_approval: dict = Field(default_factory=dict)
    operation: dict = Field(default_factory=dict)
    rollback_plan: str | None = None
    integration_readiness: list[dict] = Field(default_factory=list)
    before_state: dict = Field(default_factory=dict)
    typed_confirmation_text: str
    verification_checklist: list[str] = Field(default_factory=list)
    gates: dict = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    read_only: bool = True
