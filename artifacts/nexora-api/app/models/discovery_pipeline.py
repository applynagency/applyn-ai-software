"""Discovery scan-run model (shared by the Universal Discovery engine).

* ``DiscoveryScanRun`` — one execution of discovery for an organization. Tracks
  progress (current provider/account, resources found), diff counts, status and
  timing. Consumed by :class:`app.services.universal_discovery.UniversalDiscoveryService`.

Strictly additive platform records; read-only w.r.t. customer infrastructure.
No secrets are stored.
"""

import enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class ScanTrigger(str, enum.Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class ScanRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DiscoveryScanRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "discovery_scan_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default=ScanTrigger.MANUAL.value)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ScanRunStatus.PENDING.value, index=True
    )
    providers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    connection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_connections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # live progress
    current_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_account: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resources_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # diff outcome
    added_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    modified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
