"""Pydantic schemas for Release Reliability API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReleaseReliabilityCreate(BaseModel):
    release_id: str
    environment_id: str
    strategy: str = "rolling"
    baseline_version: str | None = None
    candidate_version: str | None = None
    artifact_digest: str | None = None
    provider_type: str = "k8s_rolling"
    deployment_id: str | None = None
    gitops_app_id: str | None = None
    rollback_plan: str | None = None


class ReleaseReliabilityView(BaseModel):
    id: str
    release_id: str
    environment_id: str
    strategy: str
    stage: str
    promotion_state: str
    verification_status: str
    baseline_version: str | None
    candidate_version: str | None
    health_gate_status: str | None
    provider_type: str
    provider_mode: str
    status: str
    timeline: list
    created_at: datetime

    model_config = {"from_attributes": True}


class RolloutPropose(BaseModel):
    strategy: str = "canary"
    provider_type: str = "k8s_rolling"
    traffic_steps: list[int] = Field(default_factory=lambda: [10, 25, 50, 100])
    target: str | None = None


class PromotionPolicyCreate(BaseModel):
    source_tier: str
    target_tier: str
    requires_verification: bool = True
    requires_security_gate: bool = True
    requires_approval: bool = True
    digest_immutable: bool = True


class PromotionPolicyView(BaseModel):
    id: str
    source_tier: str
    target_tier: str
    requires_verification: bool
    requires_security_gate: bool
    requires_approval: bool
    digest_immutable: bool
    enabled: bool

    model_config = {"from_attributes": True}


class FreezeWindowCreate(BaseModel):
    name: str
    environment_tier: str | None = None
    starts_at: datetime
    ends_at: datetime


class FreezeWindowView(BaseModel):
    id: str
    name: str
    environment_tier: str | None
    starts_at: datetime
    ends_at: datetime
    active: bool

    model_config = {"from_attributes": True}


class VerificationEvidenceView(BaseModel):
    verification_runs: list[dict]
    health_gates: list[dict]
    rollout_operations: list[dict]
    rollback_records: list[dict]
