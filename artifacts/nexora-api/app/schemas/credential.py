"""Sprint 35A — credential API schemas.

Responses NEVER include secret material. The only inbound place secrets appear
is ``CredentialCreateRequest.secret`` / ``CredentialUpdateRequest.secret``; they
are encrypted immediately and never echoed back.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.credential import CredentialProvider


class CredentialCreateRequest(BaseModel):
    provider: CredentialProvider
    name: str = Field(min_length=1, max_length=255)
    # Provider-specific secret fields, e.g. for VM:
    # {"host": ..., "port": 22, "username": ..., "private_key": ...}
    secret: dict[str, str | int] = Field(default_factory=dict)


class CredentialUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    # When provided, rotates the stored secret.
    secret: dict[str, str | int] | None = None
    is_active: bool | None = None


class CredentialResponse(BaseModel):
    id: str
    organization_id: str
    provider: str
    name: str
    is_active: bool
    # Sprint 35B — BYOI verification state (no secrets).
    status: str = "CONNECTED"
    readiness_score: int = 0
    last_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True}


class InfrastructureCheckResult(BaseModel):
    name: str
    passed: bool
    message: str


class InfrastructureValidationResponse(BaseModel):
    credential_id: str
    provider: str
    status: str
    readiness_score: int
    ready: bool
    checks: list[InfrastructureCheckResult]
    guidance: str
    last_verified_at: datetime | None = None


class CredentialListResponse(BaseModel):
    items: list[CredentialResponse]
    total: int


class SecretAccessAuditResponse(BaseModel):
    id: str
    organization_id: str
    credential_id: str | None = None
    event: str
    actor_user_id: str | None = None
    reason: str | None = None
    deployment_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecretAccessAuditListResponse(BaseModel):
    items: list[SecretAccessAuditResponse]
    total: int
