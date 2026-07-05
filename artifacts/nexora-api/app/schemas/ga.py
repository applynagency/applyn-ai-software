"""Pydantic schemas for GA readiness APIs (Sprint 64A)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InstallRunRequest(BaseModel):
    load_sample_data: bool = False
    bootstrap_admin: bool = False


class InstallRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    version: str
    readiness_score: int
    readiness_report: dict[str, Any] | None = None
    checks: list[dict[str, Any]] | None = None
    created_at: datetime


class BackupCreateRequest(BaseModel):
    label: str = "manual"
    schedule_cadence: str | None = None
    retention_days: int = Field(default=30, ge=1, le=365)


class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    storage_path: str
    encrypted: bool
    status: str
    checksum: str | None = None
    verified_at: datetime | None = None
    retention_days: int
    created_at: datetime


class SupportTokenRequest(BaseModel):
    ttl_hours: int = Field(default=24, ge=1, le=168)
    read_only: bool = True


class ReleaseChannelRequest(BaseModel):
    channel: str = Field(pattern="^(stable|preview|development)$")


class ComplianceReportRequest(BaseModel):
    framework: str


class ComplianceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    framework: str
    evidence: list[dict[str, Any]] | None = None
    gaps: list[dict[str, Any]] | None = None
    readiness_score: int
    created_at: datetime


class CustomerSuccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: str
    milestones: dict[str, bool] | None = None
    adoption_score: int
    recommendations: list[dict[str, Any]] | None = None
    setup_complete: bool
