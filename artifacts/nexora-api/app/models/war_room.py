"""Sprint 46D - AI Incident War Room.

A collaborative, multi-agent incident-response space. Specialist agents (CTO,
SRE, Kubernetes, GitHub, Database, Security) read existing incident
intelligence (40A RCA, 40B timeline, 40C change events, 41A recommendations,
42A alerts, 42C service health, 44B blast radius) and collaborate: they share
findings, challenge each other, propose hypotheses and remediation, and the
room synthesizes a consensus RCA and a remediation plan.

CRITICAL SAFETY INVARIANTS:
* The war room is advisory only. It NEVER executes remediation, deploys, rolls
  back, or mutates infrastructure or incidents.
* Human approval is always mandatory - a completed room rests in
  AWAITING_APPROVAL; nothing acts on the plan autonomously.
* Customer-safe text only; never stores secrets.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class WarRoomAuthorType(str, enum.Enum):
    AI = "AI"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class WarRoomApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class WarRoomAgent(str, enum.Enum):
    CTO = "CTO"
    SRE = "SRE"
    KUBERNETES = "KUBERNETES"
    GITHUB = "GITHUB"
    DATABASE = "DATABASE"
    SECURITY = "SECURITY"
    SYSTEM = "SYSTEM"


class WarRoomMessageType(str, enum.Enum):
    INFO = "INFO"
    FINDING = "FINDING"
    CHALLENGE = "CHALLENGE"
    HYPOTHESIS = "HYPOTHESIS"
    REMEDIATION = "REMEDIATION"
    CONSENSUS = "CONSENSUS"


class WarRoomStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_DISCUSSION = "IN_DISCUSSION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    CLOSED = "CLOSED"


class WarRoom(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "war_rooms"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("incident_investigations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=WarRoomStatus.OPEN.value, index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    consensus_rca: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    participating_agents: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Always true: a war room can never act without explicit human approval.
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class WarRoomMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "war_room_messages"

    war_room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("war_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent: Mapped[str] = mapped_column(String(20), nullable=False, default=WarRoomAgent.SYSTEM.value)
    message_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WarRoomMessageType.INFO.value
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- collaboration ---
    # Who authored the message: an AI specialist, a human participant, or SYSTEM.
    author_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WarRoomAuthorType.AI.value
    )
    # Human author (null for AI/SYSTEM messages).
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Thread root: replies point at the message they answer.
    parent_message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("war_room_messages.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Resolved mentions: [{"type": "user"|"agent", "id": ..., "label": ...}].
    mentions: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Sequence is unique within a room: prevents two concurrent posts from
    # claiming the same MAX(sequence)+1 and corrupting message ordering.
    __table_args__ = (
        UniqueConstraint("war_room_id", "sequence", name="uq_war_room_messages_seq"),
    )


class WarRoomParticipant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "war_room_participants"

    war_room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("war_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WarRoomAttachment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "war_room_attachments"

    war_room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("war_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("war_room_messages.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="UPLOAD")


class WarRoomEvidence(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "war_room_evidence"

    war_room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("war_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # An evidence item references either an uploaded attachment or an existing
    # record (incident, alert, deployment, link, ...).
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("war_room_attachments.id", ondelete="SET NULL"), nullable=True
    )
    added_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class WarRoomApproval(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "war_room_approvals"

    war_room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("war_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="REMEDIATION")
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WarRoomApprovalStatus.PENDING.value, index=True
    )
    requested_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
