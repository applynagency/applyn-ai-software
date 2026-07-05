"""Schemas for customer integration onboarding API (Sprint 67A)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OnboardingProviderInfo(BaseModel):
    provider_type: str
    display_name: str
    description: str
    required_scope_fields: list[str] = Field(default_factory=list)
    supports_pilot: bool = True


class OnboardingSessionCreate(BaseModel):
    provider_type: str
    intended_for_pilot: bool = True


class OnboardingEnvironmentUpdate(BaseModel):
    environment_name: str
    environment_classification: str
    scope: dict = Field(default_factory=dict)
    intended_for_pilot: bool = True
    api_base_url: str | None = None


class OnboardingCredentialsRequest(BaseModel):
    """Credential payload — stored via SecretManager only; never returned after submit."""

    name: str = "onboarding-credential"
    secret: dict


class OnboardingSessionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    provider_type: str
    status: str
    environment_name: str | None = None
    environment_classification: str | None = None
    scope: dict = Field(default_factory=dict)
    intended_for_pilot: bool = True
    owner_user_id: str
    credential_id: str | None = None
    validation_summary: dict = Field(default_factory=dict)
    evidence_refs: dict = Field(default_factory=dict)
    required_capabilities: list = Field(default_factory=list)
    missing_capabilities: list = Field(default_factory=list)
    readiness_verdict: str | None = None
    registry_connection_id: str | None = None
    acknowledged_at: str | None = None
    cancellation_reason: str | None = None
    api_base_url: str | None = None
    created_at: datetime
    updated_at: datetime


class OnboardingValidateResponse(BaseModel):
    session_id: str
    status: str
    validation_summary: dict = Field(default_factory=dict)
    readiness_verdict: str | None = None
    registry_connection_id: str | None = None
    missing_capabilities: list = Field(default_factory=list)
    evidence_refs: dict = Field(default_factory=dict)


class OnboardingRbacReport(BaseModel):
    session_id: str
    provider_type: str
    rbac_gaps: list[str] = Field(default_factory=list)
    prohibited_granted: list[str] = Field(default_factory=list)
    read_checks: list[dict] = Field(default_factory=list)
    scale_checks: list[dict] = Field(default_factory=list)
    inventory_summary: dict = Field(default_factory=dict)


class OnboardingLeastPrivilegeGuide(BaseModel):
    session_id: str
    provider_type: str
    guidance: dict = Field(default_factory=dict)
    minimum_rbac_yaml: str | None = None
    optional_scale_yaml: str | None = None


class OnboardingAcknowledgeRequest(BaseModel):
    acknowledged: bool = True
    acknowledgement_note: str | None = None


class OnboardingCancelRequest(BaseModel):
    reason: str


class OnboardingReadinessView(BaseModel):
    verdict: str
    checks: list[dict] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    insufficient_evidence: list[str] = Field(default_factory=list)
    remediation_steps: list[str] = Field(default_factory=list)
    sessions: list[OnboardingSessionView] = Field(default_factory=list)
    evaluated_at: str
    read_only: bool = True


class CustomerPilotPrerequisitesView(BaseModel):
    items: list[dict] = Field(default_factory=list)
    documentation_links: list[dict] = Field(default_factory=list)
