"""Commercial platform models (Sprint 61C).

Organization-scoped billing, licensing, quota and usage. Everything is
configurable — limits and feature entitlements live in JSON on the ``plans``
table (and per-org ``quota_overrides``), so there are no hardcoded limits.

Tables:
* ``plans``                 — subscription plan catalog (Free … Enterprise/Custom)
* ``subscriptions``         — one row per org (plan + lifecycle status + provider)
* ``usage_records``         — daily per-metric usage aggregates per org
* ``quota_overrides``       — per-org per-metric limit overrides
* ``licenses``              — SaaS/on-prem/offline/enterprise licenses
* ``invoices``              — manual/enterprise/Stripe invoices
* ``billing_events``        — webhook outbox (tamper-evident emission log)
* ``billing_webhook_endpoints`` — per-org outbound webhook targets
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class PlanTier(str, enum.Enum):
    FREE = "FREE"
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"
    CUSTOM = "CUSTOM"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    OVERDUE = "OVERDUE"
    GRACE = "GRACE"


class BillingProviderType(str, enum.Enum):
    STRIPE = "STRIPE"
    MANUAL = "MANUAL"
    ENTERPRISE = "ENTERPRISE"


class LicenseType(str, enum.Enum):
    SAAS = "SAAS"
    ON_PREM = "ON_PREM"
    OFFLINE = "OFFLINE"
    ENTERPRISE_CONTRACT = "ENTERPRISE_CONTRACT"


class LicenseStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAID = "PAID"
    VOID = "VOID"
    UNCOLLECTIBLE = "UNCOLLECTIBLE"


class UsageMetric(str, enum.Enum):
    """Metered dimensions. Plan limits + usage records are keyed by these."""

    API_CALLS = "api_calls"
    COPILOT_REQUESTS = "copilot_requests"
    AI_TOKENS = "ai_tokens"
    DISCOVERY_SCANS = "discovery_scans"
    WORKFLOW_EXECUTIONS = "workflow_executions"
    INTEGRATIONS = "integrations"
    ALERTS_PROCESSED = "alerts_processed"
    INCIDENTS = "incidents"
    STORAGE_BYTES = "storage_bytes"
    BACKGROUND_JOBS = "background_jobs"
    USERS = "users"
    API_KEYS = "api_keys"
    SERVICE_ACCOUNTS = "service_accounts"


class Plan(Base, UUIDMixin, TimestampMixin):
    """A subscription plan in the catalog. Limits/features are JSON so a plan is
    fully configurable without code changes (no hardcoded limits)."""

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(40), nullable=False, default=PlanTier.FREE.value)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Per-metric numeric limits, e.g. {"api_calls": 100000, "users": 25}.
    # A value of -1 (or absent) means unlimited.
    limits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Per-feature entitlements, e.g. {"sso": "enabled", "copilot": "limited"}.
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Quota policy knobs, e.g. {"soft_ratio": 0.8, "warning_ratio": 0.9,
    # "grace_days": 7, "enforcement": "hard"}.
    quota_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    billing_interval: Mapped[str] = mapped_column(String(20), nullable=False, default="month")
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    support_tier: Mapped[str] = mapped_column(String(40), nullable=False, default="community")

    # External price/product ids (Stripe etc.).
    external_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Subscription(Base, UUIDMixin, TimestampMixin):
    """One subscription per organization (plan + lifecycle + provider)."""

    __tablename__ = "subscriptions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubscriptionStatus.TRIAL.value, index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BillingProviderType.MANUAL.value,
    )

    trial_ends_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_until: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    external_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    subscription_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class UsageRecord(Base, UUIDMixin, TimestampMixin):
    """Daily per-metric usage aggregate for an organization."""

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "metric", "usage_date", name="uq_usage_org_metric_day"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    metric: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    usage_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class QuotaOverride(Base, UUIDMixin, TimestampMixin):
    """Per-org per-metric limit override (takes precedence over the plan limit)."""

    __tablename__ = "quota_overrides"
    __table_args__ = (
        UniqueConstraint("organization_id", "metric", name="uq_quota_override_org_metric"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )


class License(Base, UUIDMixin, TimestampMixin):
    """A license. Validation is signature-based and independent of Stripe."""

    __tablename__ = "licenses"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    license_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    license_type: Mapped[str] = mapped_column(String(30), nullable=False, default=LicenseType.SAAS.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=LicenseStatus.ACTIVE.value)
    plan_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    limits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    issued_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # HMAC signature over the canonical license payload (offline verification).
    signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    issued_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )


class Invoice(Base, UUIDMixin, TimestampMixin):
    """An invoice issued via any billing provider."""

    __tablename__ = "invoices"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default=BillingProviderType.MANUAL.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InvoiceStatus.OPEN.value, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    period_start: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    line_items: Mapped[list | None] = mapped_column(JSON, nullable=True)


class BillingEvent(Base, UUIDMixin, TimestampMixin):
    """Webhook outbox: every emitted commercial event is recorded then delivered."""

    __tablename__ = "billing_events"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class BillingWebhookEndpoint(Base, UUIDMixin, TimestampMixin):
    """A per-org outbound webhook target for commercial events."""

    __tablename__ = "billing_webhook_endpoints"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Subscribed event types; empty/None means all.
    events: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
