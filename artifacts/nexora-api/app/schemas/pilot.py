"""Pilot readiness API schemas (Sprint 66A)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChecklistItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section: str
    item_key: str
    title: str
    completed: bool
    owner_id: str | None = None
    evidence: dict = Field(default_factory=dict)
    blockers: list = Field(default_factory=list)
    completed_at: datetime | None = None


class PilotReadinessView(BaseModel):
    enrollment_id: str | None = None
    status: str
    readiness_score: int
    completed_items: int
    total_items: int
    blockers: list[str] = Field(default_factory=list)
    checklist: list[ChecklistItemView] = Field(default_factory=list)
    live_operations_enabled: bool = False
    onboarding_path_id: str | None = None


class OnboardingPathView(BaseModel):
    id: str
    name: str
    prerequisites: list[str]
    integrations: list[dict]
    required_capabilities: list[str]


class AssessmentRecommendation(BaseModel):
    priority: str
    action: str
    evidence: list[dict]
    source_mode: str


class PilotAssessmentView(BaseModel):
    id: str
    status: str
    summary: dict
    recommendations: list[AssessmentRecommendation]
    source_modes: dict
    created_at: datetime
    export_markdown: str | None = None


class PilotScorecardView(BaseModel):
    scores: dict
    metrics: dict
    insufficient_data: list[str]
    created_at: datetime | None = None


class LiveOperationCreate(BaseModel):
    action: str
    resource_name: str
    environment_id: str
    cluster_id: str | None = None
    namespace: str | None = "default"
    params: dict = Field(default_factory=dict)
    template_id: str | None = None
    rollback_plan: str | None = None
    idempotency_key: str | None = None


class LiveOperationConfirm(BaseModel):
    confirmation_token: str
    typed_confirmation: str
    approved: bool = True


class LiveOperationVerify(BaseModel):
    kubernetes_evidence: dict | None = None
    prometheus_evidence: dict | None = None
    events_evidence: dict | None = None


class ConfirmationTokenView(BaseModel):
    operation_id: str
    confirmation_token: str
    expires_note: str = "Present this token only to authorized operators; it is required for typed confirmation."


class LiveOperationListItemView(BaseModel):
    id: str
    action: str
    resource_name: str
    status: str
    verification_status: str | None = None
    approval_status: str | None = None
    operator_label: str
    created_at: datetime | None = None


class LiveOperationListView(BaseModel):
    items: list[LiveOperationListItemView] = Field(default_factory=list)


class LiveOperationView(BaseModel):
    id: str
    action: str
    resource_name: str
    status: str
    confirmation_token: str | None = None
    preflight: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    verification: dict = Field(default_factory=dict)
    correlation_id: str | None = None
    source_mode: str | None = None
    verification_status: str | None = None
    payload_hash: str | None = None
    execution_label: str | None = None
    template_id: str | None = None
    environment_id: str | None = None
    cluster_id: str | None = None
    params: dict = Field(default_factory=dict)
    rollback_plan: str | None = None


class PilotDiagnosticsView(BaseModel):
    integration_health: list[dict] = Field(default_factory=list)
    capability_gaps: list[dict] = Field(default_factory=list)
    validation_history: list[dict] = Field(default_factory=list)
    troubleshooting: dict = Field(default_factory=dict)
    support_token_available: bool = False
    operations_readiness: dict | None = None
    notification_health: dict | None = None


class PilotContactsUpdate(BaseModel):
    support_contact: str | None = None
    escalation_contact: str | None = None
    approval_contact: str | None = None
    approver_email: str | None = None
    nexora_operator: str | None = None
    backup_restore_acknowledged: bool | None = None


class PilotStageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stage_key: str
    title: str
    status: str
    owner_id: str | None = None
    evidence: dict = Field(default_factory=dict)
    blockers: list = Field(default_factory=list)
    rollback_plan: str | None = None
    outcome: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class PilotExecutionStatusView(BaseModel):
    enrollment_id: str
    execution_status: str
    current_stage: str | None = None
    kill_switch: bool = False
    operation_count: int = 0
    operation_limit: int = 5
    cooldown_minutes: int = 30
    stages: list[PilotStageView] = Field(default_factory=list)


class OperationTemplateView(BaseModel):
    id: str
    name: str
    action: str
    mutation: bool
    reversible: bool
    required_capabilities: list[str]
    description: str


class PilotApprovalCreate(BaseModel):
    operation_id: str
    approver_name: str
    approver_email: str
    operation_summary: str
    rollback_plan: str
    approve: bool = False


class PilotApprovalView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    operation_id: str
    approver_name: str
    approver_email: str
    operation_summary: str
    target_environment: str
    rollback_plan: str
    payload_hash: str
    status: str
    expires_at: datetime
    approved_at: datetime | None = None


class PilotApprovalDecision(BaseModel):
    approve: bool = True
    rationale: str | None = None


class PilotApprovalDecisionView(PilotApprovalView):
    decision_rationale: str | None = None


class ExecutionReadinessView(BaseModel):
    operation_id: str
    operation_status: str
    ready_for_typed_confirmation: bool
    provider_mutation_called: bool = False
    kubernetes_mutation_called: bool = False
    remaining_required_action: str
    execution_label: str
    gates: dict = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    preflight: dict = Field(default_factory=dict)


class PilotEvidencePackView(BaseModel):
    json_pack: dict
    markdown: str
    html: str


class PilotDashboardView(BaseModel):
    readiness_score: int
    execution_status: str
    integration_states: list[dict] = Field(default_factory=list)
    stages_completed: int = 0
    stages_blocked: int = 0
    approved_operations: int = 0
    verified_operations: int = 0
    failed_verifications: int = 0
    time_to_first_value_seconds: float | None = None


class KillSwitchUpdate(BaseModel):
    enabled: bool


class PilotClosureRequest(BaseModel):
    kubernetes_evidence: dict | None = None
    prometheus_evidence: dict | None = None
    events_evidence: dict | None = None
    integration_evidence: dict | None = None


class PilotClosureView(BaseModel):
    closure_status: str
    complete_advanced: bool
    verification_status: str | None = None
    enrollment_outcome: str | None = None
    execution_status: str | None = None
    operation_count: int | None = None
    operation_id: str | None = None
    blockers: list[str] = Field(default_factory=list)


class PilotLaunchReadinessView(BaseModel):
    verdict: str
    checks: list[dict] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    insufficient_evidence: list[str] = Field(default_factory=list)
    remediation_steps: list[str] = Field(default_factory=list)
    minimum_rbac: list[str] = Field(default_factory=list)
    evaluated_at: str
    read_only: bool = True
    operational_status: dict | None = None


class PilotOperationsReadinessView(BaseModel):
    verdict: str
    checks: list[dict] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    insufficient_evidence: list[str] = Field(default_factory=list)
    remediation_steps: list[str] = Field(default_factory=list)
    evaluated_at: str
    read_only: bool = True


class PilotDeploymentReadinessView(BaseModel):
    verdict: str
    checks: list[dict] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    insufficient_evidence: list[str] = Field(default_factory=list)
    remediation_steps: list[str] = Field(default_factory=list)
    operations_verdict: str | None = None
    evaluated_at: str
    read_only: bool = True
    environment: str | None = None


class PilotDryRunStatusView(BaseModel):
    completed: bool = False
    passed: bool = False
    summary: str | None = None
    steps: list[dict] = Field(default_factory=list)
    evaluated_at: str | None = None
    internal_only: bool = True


class PilotSupportBundleExportView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    json_payload: dict = Field(serialization_alias="json")
    markdown: str
    html: str
    pdf_base64: str | None = None
    redacted: bool = True
    export_blocked: bool = False
    block_reason: str | None = None
