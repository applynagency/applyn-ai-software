"""Sprint 45A — Intelligent Runbooks.

A ``Runbook`` is an investigation + remediation playbook for a class of incident
(Kubernetes, deployment failure, CrashLoopBackOff, latency spike, error spike,
capacity). It is *generated read-only* from existing incident intelligence —
RCA (40A), timeline (40B), recommendations (41A), remediation actions (41B/41C),
and postmortems (44A) — and then can be manually edited and versioned.

Generation never mutates incidents; it only reads them and writes its own record.
Org-scoped, audited, no secrets.
"""

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class RunbookCategory(str, enum.Enum):
    KUBERNETES = "KUBERNETES"
    DEPLOYMENT_FAILURE = "DEPLOYMENT_FAILURE"
    CRASHLOOPBACKOFF = "CRASHLOOPBACKOFF"
    LATENCY_SPIKE = "LATENCY_SPIKE"
    ERROR_SPIKE = "ERROR_SPIKE"
    CAPACITY = "CAPACITY"
    GENERAL = "GENERAL"


class RunbookStatus(str, enum.Enum):
    GENERATED = "GENERATED"
    REGENERATED = "REGENERATED"
    EDITED = "EDITED"


class RunbookSource(str, enum.Enum):
    GENERATED = "GENERATED"
    MANUAL = "MANUAL"


class Runbook(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "runbooks"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(40), nullable=False, default=RunbookCategory.GENERAL.value, index=True
    )
    service: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ordered step lists (each a list of plain strings — easy to edit manually).
    investigation_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    validation_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rollback_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recovery_checklist: Mapped[list | None] = mapped_column(JSON, nullable=True)

    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lowercased haystack of title/category/service/summary/steps for search.
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Incidents the runbook learned from.
    source_incident_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RunbookStatus.GENERATED.value
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RunbookSource.GENERATED.value
    )

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
