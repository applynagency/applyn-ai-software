"""Integration readiness API schemas (Sprint 65G)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderSummary(BaseModel):
    provider_type: str
    total: int = 0
    connected: int = 0
    degraded: int = 0
    failed: int = 0


class ConnectionReadinessView(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    provider_type: str
    credential_id: str | None = None
    lifecycle_state: str
    provider_mode: str
    capabilities: dict = Field(default_factory=dict)
    health_score: int = 0
    failure_reason: str | None = None
    last_validated_at: datetime | None = None
    last_successful_at: datetime | None = None
    reauth_required: bool = False
    validation_metadata: dict = Field(default_factory=dict)
    feature_impact: list[str] = Field(default_factory=list)
    remediation: str | None = None


class ValidateResponse(BaseModel):
    connection_id: str
    lifecycle_state: str
    provider_mode: str
    health_score: int
    capabilities: dict
    failure_reason: str | None = None
    latency_ms: int | None = None
    guidance: str | None = None


class CapabilitiesView(BaseModel):
    connection_id: str
    capabilities: dict
    provider_mode: str
    lifecycle_state: str
    write_allowed: bool


class HealthView(BaseModel):
    connection_id: str
    lifecycle_state: str
    provider_mode: str
    health_score: int
    consecutive_failures: int
    last_validated_at: datetime | None = None
    last_successful_at: datetime | None = None
    failure_reason: str | None = None
    reauth_required: bool = False


class HealthHistoryEntry(BaseModel):
    id: str
    previous_state: str | None
    new_state: str
    probe_result: dict
    latency_ms: int | None = None
    created_at: datetime


class ExpiryReminderView(BaseModel):
    id: str
    warning_level: str
    expires_at: datetime | None = None
    acknowledged: bool = False
    snoozed_until: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class ExpiryAckRequest(BaseModel):
    reminder_id: str | None = None


class ExpirySnoozeRequest(BaseModel):
    reminder_id: str | None = None
    days: int = Field(default=7, ge=1, le=90)


class IntegrationDashboard(BaseModel):
    total: int = 0
    connected: int = 0
    degraded: int = 0
    failed: int = 0
    expired: int = 0
    reauth_required: int = 0
    last_validation: datetime | None = None
    capability_gaps: list[dict] = Field(default_factory=list)
    upcoming_expiry: list[dict] = Field(default_factory=list)
    affected_features: list[str] = Field(default_factory=list)
    remediation_hints: list[str] = Field(default_factory=list)


class TestNotificationRequest(BaseModel):
    channel: str = "slack"
    connection_id: str | None = None
    dry_run: bool = True


class IntegrationReadinessContext(BaseModel):
    connection_id: str | None = None
    state: str | None = None
    provider_mode: str | None = None
    last_validated_at: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    preflight_status: str | None = None
    blocked_reason: str | None = None
    remediation_guidance: str | None = None
    correlation_id: str | None = None
    simulated: bool = False
