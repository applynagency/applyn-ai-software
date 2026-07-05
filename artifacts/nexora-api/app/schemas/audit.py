"""Schemas for the audit log API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    organization_id: str | None
    sequence: int | None
    user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict | None
    ip_address: str | None
    user_agent: str | None
    status: str
    entry_hash: str | None
    prev_hash: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    offset: int
    limit: int


class AuditIntegrityError(BaseModel):
    id: str
    sequence: int | None
    error: str


class AuditIntegrityResponse(BaseModel):
    organization_id: str | None
    total: int
    verified: int
    legacy_unhashed: int
    valid: bool
    errors: list[AuditIntegrityError]
    first_sequence: int | None
    last_sequence: int | None


class AuditRetentionResponse(BaseModel):
    deleted: int
    retention_days: int
    cutoff: datetime | None
