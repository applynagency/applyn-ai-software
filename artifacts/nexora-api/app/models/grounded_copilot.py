"""Grounded Copilot — conversation persistence.

A ``GroundedCopilotConversation`` groups a multi-turn conversation;
``GroundedCopilotMessage`` stores each turn. Assistant turns record the grounded
answer plus the evidence it was built from: citations (source records), the tools
invoked, the RAG/graph sources retrieved, a confidence score, a ``grounded`` flag
(set by hallucination-prevention validation), and the generation mode
(``live`` / ``offline`` / ``fallback``).

The copilot is read-only: it never executes mutating actions and never returns
secrets.
"""

import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class GroundedCopilotRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class GroundedCopilotConversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "copilot_conversations"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class GroundedCopilotMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "copilot_messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GroundedCopilotRole.USER.value
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- grounding evidence (assistant turns) ---
    intent: Mapped[str | None] = mapped_column(String(60), nullable=True)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grounded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    generation_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
