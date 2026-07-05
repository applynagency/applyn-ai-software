"""Pydantic schemas for the commercial platform (Sprint 61C)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Plans -------------------------------------------------------------------
class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    tier: str
    description: str | None = None
    is_active: bool
    is_public: bool
    limits: dict | None = None
    features: dict | None = None
    quota_policy: dict | None = None
    price_cents: int
    currency: str
    billing_interval: str
    trial_days: int
    support_tier: str


class PlanListResponse(BaseModel):
    items: list[PlanResponse]
    total: int


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = None
    tier: str = "CUSTOM"
    description: str | None = None
    is_active: bool = True
    is_public: bool = True
    limits: dict | None = None
    features: dict | None = None
    quota_policy: dict | None = None
    price_cents: int = 0
    currency: str = "USD"
    billing_interval: str = "month"
    trial_days: int = 0
    support_tier: str = "community"
    external_price_id: str | None = None


class PlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tier: str | None = None
    is_active: bool | None = None
    is_public: bool | None = None
    limits: dict | None = None
    features: dict | None = None
    quota_policy: dict | None = None
    price_cents: int | None = None
    currency: str | None = None
    billing_interval: str | None = None
    trial_days: int | None = None
    support_tier: str | None = None
    external_price_id: str | None = None


class PlanCloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = None


# --- Subscriptions -----------------------------------------------------------
class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    plan_id: str
    status: str
    provider: str
    trial_ends_at: datetime | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    grace_until: datetime | None = None
    cancelled_at: datetime | None = None


class AssignPlanRequest(BaseModel):
    plan_id: str
    provider: str | None = None


class SuspendRequest(BaseModel):
    reason: str | None = None


# --- Quota / usage -----------------------------------------------------------
class QuotaOverrideRequest(BaseModel):
    metric: str
    limit_value: int
    note: str | None = None


class UsageDashboardResponse(BaseModel):
    organization_id: str
    plan: dict
    subscription: dict
    metrics: list[dict]
    overages: list[dict]
    features: dict


# --- Licenses ----------------------------------------------------------------
class LicenseIssueRequest(BaseModel):
    organization_id: str | None = None
    license_type: str = "SAAS"
    plan_slug: str | None = None
    seats: int = 0
    features: dict | None = None
    limits: dict | None = None
    expires_at: datetime | None = None


class LicenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str | None = None
    license_key: str
    license_type: str
    status: str
    plan_slug: str | None = None
    seats: int
    issued_at: datetime | None = None
    expires_at: datetime | None = None


class LicenseIssuedResponse(LicenseResponse):
    offline_token: str


class LicenseValidateRequest(BaseModel):
    license_key: str | None = None
    offline_token: str | None = None


# --- Webhooks ----------------------------------------------------------------
class WebhookEndpointCreate(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    secret: str | None = None
    events: list[str] | None = None


class WebhookEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    url: str
    events: list | None = None
    is_active: bool


# --- Feature flags -----------------------------------------------------------
class FeatureFlagsResponse(BaseModel):
    organization_id: str
    flags: dict


# --- Invoices (org admin read-only) ------------------------------------------
class InvoiceResponse(BaseModel):
    """Org-safe invoice row — no provider IDs, line items, or raw metadata."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    status: str
    amount_cents: int
    currency: str
    period_start: datetime | None = None
    period_end: datetime | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    offset: int
    limit: int
