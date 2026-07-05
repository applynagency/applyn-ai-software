"""Platform convergence models (Sprint 62A).

One canonical implementation for the cross-cutting platform capabilities:

* ``domain_events``          — first-class event store / outbox (publish + replay + DLQ)
* ``notification_templates`` — channel templates (global + org overrides, localized)
* ``notification_messages``  — outbound deliveries with retries + delivery tracking
* ``activity_entries``       — unified activity feed (per org / user / resource)
* ``config_entries``         — global → organization → user settings + feature flags
* ``plugins``                — installable plugin catalog (capabilities manifest)
* ``organization_plugins``   — per-org plugin installation + lifecycle state
* ``execution_checkpoints``  — unified execution-engine checkpoints (resume)

All tables are organization-scoped where applicable and follow the standard
``Base/UUIDMixin/TimestampMixin`` conventions.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


# --------------------------------------------------------------------------- #
# Event bus / domain events
# --------------------------------------------------------------------------- #
class EventStatus(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    PROCESSED = "processed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class DomainEvent(Base, UUIDMixin, TimestampMixin):
    """Durable event record — the outbox + audit + replay log of the event bus."""

    __tablename__ = "domain_events"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    aggregate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="platform")
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=EventStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Sprint 62B — exactly-once / idempotent replication. When set, a second
    # publish with the same key is a no-op (returns the existing event), so retries
    # and cross-region replication never double-deliver.
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # When this leader-elected consumer last claimed the event (durable consumer).
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_domain_events_org_type", "organization_id", "event_type"),
        Index("ix_domain_events_status_created", "status", "created_at"),
        Index("ix_domain_events_aggregate", "aggregate_type", "aggregate_id"),
        UniqueConstraint("idempotency_key", name="uq_domain_events_idempotency"),
    )


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
class NotificationTemplate(Base, UUIDMixin, TimestampMixin):
    """A channel template. ``organization_id`` null => global; non-null => override."""

    __tablename__ = "notification_templates"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    subject_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "key", "channel", "locale",
                         name="uq_notif_template_scope"),
        Index("ix_notification_templates_key", "key"),
    )


class NotificationMessage(Base, UUIDMixin, TimestampMixin):
    """An outbound notification with retry + delivery tracking."""

    __tablename__ = "notification_messages"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    template_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_notification_messages_org_status", "organization_id", "status"),
    )


# --------------------------------------------------------------------------- #
# Activity feed
# --------------------------------------------------------------------------- #
class ActivityEntry(Base, UUIDMixin, TimestampMixin):
    """A unified activity-feed entry, typically produced from a domain event."""

    __tablename__ = "activity_entries"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    verb: Mapped[str] = mapped_column(String(60), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_activity_entries_org_created", "organization_id", "created_at"),
        Index("ix_activity_entries_actor", "actor_id", "created_at"),
        Index("ix_activity_entries_object", "object_type", "object_id"),
    )


# --------------------------------------------------------------------------- #
# Configuration platform
# --------------------------------------------------------------------------- #
class ConfigScope(str, enum.Enum):
    GLOBAL = "global"
    ORGANIZATION = "organization"
    USER = "user"


class ConfigEntry(Base, UUIDMixin, TimestampMixin):
    """A single setting at a scope. Resolution: global < organization < user."""

    __tablename__ = "config_entries"

    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    # null for global; org id for organization; user id for user scope.
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="json")
    is_feature_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_secret_ref: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "key", name="uq_config_scope_key"),
        Index("ix_config_entries_lookup", "scope", "scope_id", "key"),
    )


# --------------------------------------------------------------------------- #
# Plugin framework
# --------------------------------------------------------------------------- #
class Plugin(Base, UUIDMixin, TimestampMixin):
    """A plugin catalog entry (global). Capabilities described by the manifest."""

    __tablename__ = "plugins"

    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # capability manifest: {"tools":[], "pages":[], "apis":[], "events":[], "ai_tools":[]}
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_listed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OrganizationPlugin(Base, UUIDMixin, TimestampMixin):
    """Per-org plugin installation + lifecycle state."""

    __tablename__ = "organization_plugins"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    plugin_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="installed")
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    installed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "plugin_slug", name="uq_org_plugin"),
        Index("ix_organization_plugins_org", "organization_id", "status"),
    )


# --------------------------------------------------------------------------- #
# Unified execution engine
# --------------------------------------------------------------------------- #
class ExecutionCheckpoint(Base, UUIDMixin, TimestampMixin):
    """A durable checkpoint for the unified execution engine (resume support)."""

    __tablename__ = "execution_checkpoints"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_checkpoint_job_seq"),
        Index("ix_execution_checkpoints_job", "job_id", "sequence"),
    )


# --------------------------------------------------------------------------- #
# Search platform (Sprint 62B) — incremental index + analytics
# --------------------------------------------------------------------------- #
class SearchDocument(Base, UUIDMixin, TimestampMixin):
    """A denormalized, incrementally-maintained search document.

    One row per indexed entity (incident, service, asset, …). Maintained
    incrementally as entities change (no full rebuilds during normal operation);
    a background cron reconciles drift. ``keywords`` is a lowercase token bag used
    for typo-tolerant / weighted matching.
    """

    __tablename__ = "search_documents"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    weight: Mapped[float] = mapped_column(default=1.0, nullable=False)
    # Mirror of the source row's updated_at so reindex can detect drift cheaply.
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_search_doc_entity"),
        Index("ix_search_documents_org_type", "organization_id", "entity_type"),
    )


class SearchQueryLog(Base, UUIDMixin, TimestampMixin):
    """Search analytics: every query, its result count and latency."""

    __tablename__ = "search_query_logs"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    query: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    normalized_query: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    took_ms: Mapped[float] = mapped_column(default=0.0, nullable=False)
    profile: Mapped[str | None] = mapped_column(String(40), nullable=True)

    __table_args__ = (
        Index("ix_search_query_logs_org_created", "organization_id", "created_at"),
        Index("ix_search_query_logs_norm", "normalized_query"),
    )


# --------------------------------------------------------------------------- #
# Product excellence (Sprint 63A)
# --------------------------------------------------------------------------- #
class InboxNotification(Base, UUIDMixin, TimestampMixin):
    """In-app notification center entry (distinct from outbound channel messages)."""

    __tablename__ = "inbox_notifications"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    group_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_inbox_notifications_user_read", "user_id", "read_at", "created_at"),
        Index("ix_inbox_notifications_org_user", "organization_id", "user_id"),
    )


class SavedView(Base, UUIDMixin, TimestampMixin):
    """A saved filter, search, dashboard preset or layout."""

    __tablename__ = "saved_views"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    view_type: Mapped[str] = mapped_column(String(30), nullable=False, default="filter")
    definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_saved_views_org_user", "organization_id", "user_id"),
    )


class DashboardLayout(Base, UUIDMixin, TimestampMixin):
    """A drag-and-drop dashboard layout with widget definitions."""

    __tablename__ = "dashboard_layouts"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    widgets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_dashboard_layouts_org_user", "organization_id", "user_id"),
    )


class ReportSchedule(Base, UUIDMixin, TimestampMixin):
    """Scheduled report generation + delivery."""

    __tablename__ = "report_schedules"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False, default="executive")
    cadence: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    export_format: Mapped[str] = mapped_column(String(10), nullable=False, default="pdf")
    delivery_channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    delivery_target: Mapped[str] = mapped_column(String(320), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_report_schedules_org_enabled", "organization_id", "enabled"),
    )


class CollaborationComment(Base, UUIDMixin, TimestampMixin):
    """Threaded comment on any platform resource."""

    __tablename__ = "collaboration_comments"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("collaboration_comments.id", ondelete="CASCADE"), nullable=True)
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_collab_comments_resource", "resource_type", "resource_id", "created_at"),
    )


class CollaborationReaction(Base, UUIDMixin, TimestampMixin):
    """Emoji reaction on a comment or resource."""

    __tablename__ = "collaboration_reactions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("collaboration_comments.id", ondelete="CASCADE"), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        Index("ix_collab_reactions_comment", "comment_id"),
        Index("ix_collab_reactions_resource", "resource_type", "resource_id"),
    )


class ProductAnalyticsEvent(Base, UUIDMixin, TimestampMixin):
    """Privacy-aware product analytics event (org-scoped, no raw PII in properties)."""

    __tablename__ = "product_analytics_events"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    session_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_product_analytics_org_event", "organization_id", "event_name", "created_at"),
    )
