"""Sprint 58A.3 — Monitoring ingestion dead-letter queue.

When a provider poll or webhook payload cannot be ingested after retries, the
failure is recorded here (customer-safe: provider, source, error, attempt count,
and a digest of the payload — never the raw payload or any secret) so operators
can inspect and replay it without losing the signal.
"""

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class DeadLetterSource(str, enum.Enum):
    POLL = "POLL"
    WEBHOOK = "WEBHOOK"


class DeadLetterStatus(str, enum.Enum):
    PENDING = "PENDING"
    REPLAYED = "REPLAYED"
    DISCARDED = "DISCARDED"


class MonitoringDeadLetter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "monitoring_dead_letters"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=DeadLetterSource.POLL.value)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeadLetterStatus.PENDING.value, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
