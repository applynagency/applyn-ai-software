"""Pydantic schemas for Enterprise Security Platform API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    kind: str
    target: str
    tool: str | None = None
    config: dict = Field(default_factory=dict)
    enforce_gate: bool = False


class ScanRunView(BaseModel):
    id: str
    kind: str
    tool: str
    target: str
    status: str
    summary: dict
    simulated: bool
    gate_decision: str | None
    provider_mode: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingView(BaseModel):
    id: str
    source: str
    severity: str
    status: str
    title: str
    resource: str | None
    service: str | None
    cve: str | None
    cvss_score: float | None
    remediation_guidance: str | None
    fingerprint: str
    source_system: str | None = None
    imported_at: datetime | None = None
    sla_due_at: datetime | None = None
    sla_breached: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingTransition(BaseModel):
    status: str
    reason: str | None = None


class ExceptionCreate(BaseModel):
    finding_id: str
    justification: str
    expires_at: datetime


class ExceptionView(BaseModel):
    id: str
    finding_id: str
    justification: str
    expires_at: datetime
    status: str

    model_config = {"from_attributes": True}


class RemediationProposalCreate(BaseModel):
    finding_id: str
    kind: str
    title: str
    impact: str | None = None
    rollback_plan: str | None = None


class RemediationProposalView(BaseModel):
    id: str
    finding_id: str
    kind: str
    title: str
    risk: str
    status: str
    requires_approval: bool
    rollback_plan: str | None

    model_config = {"from_attributes": True}


class OverviewView(BaseModel):
    posture_score: int
    grade: str
    open_critical: int
    open_findings: int
    recent_scans: int
    pending_remediations: int


class AnalyticsView(BaseModel):
    posture_score: int
    grade: str
    by_severity: dict
    by_source: dict
    sla_breaches: int
    trend: list


class InvestigationCreate(BaseModel):
    title: str | None = None
    incident_id: str | None = None


class InvestigationView(BaseModel):
    id: str
    title: str
    timeline: dict
    summary: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SbomView(BaseModel):
    id: str
    format: str
    target: str
    component_count: int

    model_config = {"from_attributes": True}


class ComplianceView(BaseModel):
    score: int
    grade: str
    frameworks: list
    findings: list


class IdentitySecurityView(BaseModel):
    campaigns: list
    findings: list


class ProvidersView(BaseModel):
    scan_kinds: list[str]
    delivery_tools: list[str]


class ProviderCreate(BaseModel):
    provider_type: str
    name: str
    enabled: bool = False
    config: dict = Field(default_factory=dict)


class ProviderView(BaseModel):
    id: str
    provider_type: str
    name: str
    enabled: bool
    mode: str
    validated_at: datetime | None = None
    validation_message: str | None = None

    model_config = {"from_attributes": True}


class SbomImportRequest(BaseModel):
    format: str = "cyclonedx"
    target: str
    content: dict
    artifact_id: str | None = None


class SbomComponentView(BaseModel):
    id: str
    name: str
    version: str | None
    ecosystem: str | None
    license: str | None
    purl: str | None
    vuln_finding_ids: list = Field(default_factory=list)

    model_config = {"from_attributes": True}


class BackfillStatusView(BaseModel):
    id: str | None = None
    status: str
    dry_run: bool
    counts: dict
    completed_at: datetime | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class SlaView(BaseModel):
    policies: list[dict]
    dashboard: dict


class RemediationExecutionView(BaseModel):
    id: str
    proposal_id: str
    status: str
    execution_job_id: str | None
    checkpoints: list
    result: dict
    verification: dict
    created_at: datetime

    model_config = {"from_attributes": True}
