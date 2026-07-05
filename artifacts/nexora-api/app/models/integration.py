"""Sprint 47B - Integration Marketplace.

A centralized marketplace listing every supported integration (clouds, source
control, observability, incident, communication, project tools) and the
customer's live connections to them.

* ``integration_catalog`` - the catalogue of supported integrations. Seeded as
  global rows (``organization_id`` NULL) from static definitions.
* ``integration_connections`` - a customer's connection to a catalogue entry.
  Secrets are NEVER stored here; the connection references a 35A
  ``deployment_credentials`` row (AES-256-GCM envelope) via ``credential_id``.

Read-only verification only: marketplace checks credential configuration and
granted read scopes; it never mutates or acts on the remote system. No secrets.
"""

import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class IntegrationCategory(str, enum.Enum):
    CLOUD = "CLOUD"
    ORCHESTRATION = "ORCHESTRATION"
    SOURCE_CONTROL = "SOURCE_CONTROL"
    OBSERVABILITY = "OBSERVABILITY"
    INCIDENT = "INCIDENT"
    COMMUNICATION = "COMMUNICATION"
    PROJECT = "PROJECT"


class ConnectionStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"  # credentials saved, not yet verified
    VERIFIED = "VERIFIED"  # connectivity + permissions verified (read-only)
    NEEDS_ATTENTION = "NEEDS_ATTENTION"  # verification failed / action required
    DISCONNECTED = "DISCONNECTED"  # inactive / revoked


class ConnectionHealth(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class IntegrationCatalog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_catalog"

    # Global catalogue rows use NULL organization_id (shared by all tenants).
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    integration_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default=IntegrationCategory.CLOUD.value)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_type: Mapped[str] = mapped_column(String(40), nullable=False, default="TOKEN")
    required_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    capabilities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    docs_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IntegrationConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_connections"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Encrypted secret lives in deployment_credentials (35A) - referenced, never inlined.
    credential_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("deployment_credentials.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ConnectionStatus.CONNECTED.value, index=True
    )
    health: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConnectionHealth.UNKNOWN.value
    )
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    permissions_granted: Mapped[list | None] = mapped_column(JSON, nullable=True)
    verification_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_verified_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
