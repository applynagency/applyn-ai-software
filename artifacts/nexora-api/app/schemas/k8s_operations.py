"""Pydantic schemas for Advanced Kubernetes Operations API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class K8sReadRequest(BaseModel):
    action: str
    namespace: str | None = None
    name: str | None = None
    kind: str | None = None
    params: dict = Field(default_factory=dict)


class K8sOverviewView(BaseModel):
    cluster: dict
    health_score: dict
    resource_counts: dict
    pending_operations: int


class DiagnosticsCollect(BaseModel):
    namespace: str
    name: str
    kind: str = "Pod"


class DiagnosticsBundleView(BaseModel):
    id: str
    cluster_id: str
    namespace: str | None
    resource_kind: str
    resource_name: str
    bundle: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class K8sOperationCreate(BaseModel):
    """Mutation proposal — cluster_id comes from the URL path."""
    kind: str
    namespace: str | None = None
    resource_name: str | None = None
    params: dict = Field(default_factory=dict)
