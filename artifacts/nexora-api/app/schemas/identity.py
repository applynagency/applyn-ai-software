"""Pydantic schemas for the enterprise identity & access API.

Secret material (API key plaintext, TOTP secret, recovery codes) is returned
exactly once on creation and never echoed by read endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.identity import ApiKeyPrincipalType
from app.models.organization import OrganizationRole

# --- API keys ----------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] | None = None
    expires_at: datetime | None = None


class PersonalApiKeyCreate(ApiKeyCreate):
    pass


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    principal_type: ApiKeyPrincipalType
    name: str
    prefix: str
    scopes: list[str] | None = None
    organization_id: str | None = None
    user_id: str | None = None
    service_account_id: str | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class ApiKeyWithSecret(ApiKeyResponse):
    api_key: str = Field(description="The plaintext key — shown only once")


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyResponse]
    total: int


# --- Service accounts --------------------------------------------------------


class ServiceAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    role: OrganizationRole = OrganizationRole.VIEWER
    scopes: list[str] | None = None
    expires_at: datetime | None = None


class ServiceAccountUpdate(BaseModel):
    description: str | None = None
    role: OrganizationRole | None = None
    scopes: list[str] | None = None
    disabled: bool | None = None
    expires_at: datetime | None = None
    clear_expiry: bool = False


class ServiceAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: str | None = None
    role: str
    scopes: list[str] | None = None
    disabled: bool
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime


class ServiceAccountListResponse(BaseModel):
    items: list[ServiceAccountResponse]
    total: int


# --- Sessions ----------------------------------------------------------------


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    device_label: str | None = None
    rotation_count: int
    last_seen_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    current: bool = False


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int


class RevokeResult(BaseModel):
    revoked: int


# --- Security policy ---------------------------------------------------------


class SecurityPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: str
    password_min_length: int
    password_require_uppercase: bool
    password_require_lowercase: bool
    password_require_number: bool
    password_require_symbol: bool
    mfa_required: bool
    session_timeout_minutes: int
    max_concurrent_sessions: int
    allowed_email_domains: list[str] | None = None
    ip_allowlist: list[str] | None = None
    api_keys_enabled: bool
    api_key_max_age_days: int


class SecurityPolicyUpdate(BaseModel):
    password_min_length: int | None = Field(default=None, ge=1, le=256)
    password_require_uppercase: bool | None = None
    password_require_lowercase: bool | None = None
    password_require_number: bool | None = None
    password_require_symbol: bool | None = None
    mfa_required: bool | None = None
    session_timeout_minutes: int | None = Field(default=None, ge=0)
    max_concurrent_sessions: int | None = Field(default=None, ge=0)
    allowed_email_domains: list[str] | None = None
    ip_allowlist: list[str] | None = None
    api_keys_enabled: bool | None = None
    api_key_max_age_days: int | None = Field(default=None, ge=0)


# --- MFA ---------------------------------------------------------------------


class MfaEnrollResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=10)


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=14)


class MfaStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


# --- Scope catalog -----------------------------------------------------------


class ScopeCatalogResponse(BaseModel):
    scopes: dict[str, str]
