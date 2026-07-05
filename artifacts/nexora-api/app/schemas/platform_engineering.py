"""Pydantic schemas for Platform Engineering API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IaCRepositoryCreate(BaseModel):
    name: str
    provider: str
    url: str | None = None
    default_branch: str = "main"
    working_dir: str = "."
    credential_id: str | None = None


class IaCRepositoryView(BaseModel):
    id: str
    name: str
    provider: str
    url: str | None
    default_branch: str
    working_dir: str

    model_config = {"from_attributes": True}


class IaCStackCreate(BaseModel):
    name: str
    provider: str
    repository_id: str | None = None
    variables: dict = Field(default_factory=dict)
    secret_refs: list = Field(default_factory=list)
    state_backend: str | None = None
    cloud_account_id: str | None = None
    cluster_id: str | None = None


class IaCStackView(BaseModel):
    id: str
    name: str
    provider: str
    repository_id: str | None
    variables: dict
    state_metadata: dict | None
    outputs: dict | None
    cloud_account_id: str | None
    cluster_id: str | None

    model_config = {"from_attributes": True}


class IaCRunCreate(BaseModel):
    kind: str
    variables: dict | None = None


class IaCRunView(BaseModel):
    id: str
    stack_id: str
    kind: str
    status: str
    plan_summary: dict | None
    outputs: dict | None
    logs: str | None
    error: str | None
    execution_job_id: str | None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class PlatformTemplateView(BaseModel):
    id: str
    kind: str
    name: str
    description: str | None
    spec: dict
    is_builtin: bool

    model_config = {"from_attributes": True}


class EnvironmentCreate(BaseModel):
    name: str
    tier: str
    template_id: str | None = None
    cloud_account_id: str | None = None


class EnvironmentView(BaseModel):
    id: str
    name: str
    tier: str
    template_id: str | None
    status: str
    stack_id: str | None
    cluster_id: str | None
    components: dict

    model_config = {"from_attributes": True}


class ProvisionCreate(BaseModel):
    template_kind: str
    distribution: str
    environment_id: str | None = None
    cloud_account_id: str | None = None


class ProvisionView(BaseModel):
    id: str
    template_kind: str
    distribution: str
    status: str
    progress_percent: int
    logs: str | None
    outputs: dict | None
    error: str | None
    cluster_id: str | None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class SecretRefCreate(BaseModel):
    name: str
    backend: str
    path: str
    stack_id: str | None = None
    environment_id: str | None = None
    rotation_days: int | None = None


class SecretRefView(BaseModel):
    id: str
    name: str
    backend: str
    path: str
    rotation_days: int | None
    last_rotated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CatalogItemView(BaseModel):
    id: str
    kind: str
    name: str
    description: str | None
    spec: dict
    requires_approval: bool

    model_config = {"from_attributes": True}


class CatalogRequestCreate(BaseModel):
    catalog_item_id: str
    params: dict = Field(default_factory=dict)


class CatalogRequestView(BaseModel):
    id: str
    catalog_item_id: str
    status: str
    params: dict
    requested_by: str
    approved_by: str | None

    model_config = {"from_attributes": True}


class GoldenTemplateCreate(BaseModel):
    kind: str
    name: str
    description: str | None = None


class GoldenTemplateView(BaseModel):
    id: str
    kind: str
    name: str
    description: str | None
    spec: dict

    model_config = {"from_attributes": True}


class ComplianceReportView(BaseModel):
    id: str
    score: int
    grade: str
    findings: list
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class DriftFindingView(BaseModel):
    id: str
    source: str
    resource: str
    message: str
    severity: str
    recommendation: str
    ai_explanation: str | None
    acknowledged: bool

    model_config = {"from_attributes": True}


class DashboardView(BaseModel):
    repositories: int
    stacks: int
    environments: int
    pending_approvals: int
    active_drift: int
    latest_compliance_score: int | None
