"""Sprint 35A — credential & secret-access models.

`deployment_credentials` stores customer infrastructure secrets ONLY as an
AES-256-GCM ciphertext envelope in ``encrypted_payload``. There are deliberately
no per-field plaintext columns (no client_secret/private_key/kubeconfig/etc.).

`secret_access_audit` records every lifecycle/usage event for a credential.
"""

import enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class CredentialProvider(str, enum.Enum):
    AZURE = "AZURE"
    AWS = "AWS"
    KUBERNETES = "KUBERNETES"
    VM = "VM"
    # Sprint 39C — additional read-only investigation providers. These reuse the
    # same encrypted credential store; the provider column is free-form String so
    # no migration is required to add them.
    GITHUB = "GITHUB"
    POSTGRESQL = "POSTGRESQL"
    PROMETHEUS = "PROMETHEUS"
    GRAFANA = "GRAFANA"
    DATADOG = "DATADOG"
    GCP = "GCP"


class InfrastructureStatus(str, enum.Enum):
    """Sprint 35B — customer-facing infrastructure connection status."""

    CONNECTED = "CONNECTED"  # credentials saved, not yet verified
    VERIFIED = "VERIFIED"  # connection + permissions + health checks passed
    VERIFICATION_FAILED = "VERIFICATION_FAILED"  # last verification did not pass
    DISCONNECTED = "DISCONNECTED"  # revoked/inactive


class SecretAuditEvent(str, enum.Enum):
    SECRET_CREATED = "SECRET_CREATED"
    SECRET_UPDATED = "SECRET_UPDATED"
    SECRET_USED = "SECRET_USED"
    SECRET_REVOKED = "SECRET_REVOKED"


class DeploymentCredential(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_credentials"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # AES-256-GCM ciphertext envelope ("v1:<base64...>"). NEVER plaintext.
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Sprint 35B — BYOI verification state (no secrets stored here).
    status: Mapped[str] = mapped_column(
        String(30), default=InfrastructureStatus.CONNECTED.value, nullable=False
    )
    readiness_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_verified_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Customer-safe check results only ({name, passed, message}); never secrets.
    verification_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    last_used_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SecretAccessAudit(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "secret_access_audit"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credential_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("deployment_credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
