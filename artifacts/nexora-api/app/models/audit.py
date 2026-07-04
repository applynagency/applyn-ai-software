"""Tamper-evident audit log.

Audit entries are **append-only** and chained per organization with a SHA-256
hash chain (each entry hashes its own canonical content including the previous
entry's hash). Any modification, deletion or reordering breaks the chain and is
detected by integrity verification.

Immutability is enforced at the ORM layer: ``UPDATE`` and (ORM) ``DELETE`` on an
``AuditLog`` raise ``AuditImmutableError``. Retention purge uses a separate,
sanctioned core bulk-delete path.
"""

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class AuditImmutableError(Exception):
    """Raised on any attempt to UPDATE or ORM-DELETE an audit entry."""


class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    # Tenant scope (None = system/global chain). Indexed for org-scoped queries.
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)

    # --- hash chain (per organization) ---
    # Monotonic position within the organization's chain (0 = genesis).
    sequence: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # SHA-256 hex of this entry's canonical content (includes prev_hash).
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # entry_hash of the previous entry in the same chain (None for genesis).
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")  # noqa: F821


@event.listens_for(AuditLog, "before_update", propagate=True)
def _block_audit_update(mapper, connection, target):  # noqa: ANN001
    raise AuditImmutableError("Audit log entries are immutable and cannot be updated")


@event.listens_for(AuditLog, "before_delete", propagate=True)
def _block_audit_delete(mapper, connection, target):  # noqa: ANN001
    raise AuditImmutableError(
        "Audit log entries are immutable; deletion is only permitted via retention purge"
    )
