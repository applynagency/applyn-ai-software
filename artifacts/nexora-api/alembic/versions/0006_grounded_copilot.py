"""Grounded copilot conversation tables.

Revision ID: 0006_grounded_copilot
Revises: 0005_audit
Create Date: 2026-06-29

Creates ``copilot_conversations`` and ``copilot_messages`` for the grounded LLM
copilot. Uses the idempotent ORM ``create(checkfirst=True)`` pattern: a fresh
``alembic upgrade head`` already has the tables (squashed ``0001_baseline``
builds the schema from live ORM metadata), while a previously-stamped database
gets them created here.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_grounded_copilot"
down_revision: str | None = "0005_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.models.grounded_copilot import (
        GroundedCopilotConversation,
        GroundedCopilotMessage,
    )

    bind = op.get_bind()
    for model in (GroundedCopilotConversation, GroundedCopilotMessage):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    from app.models.grounded_copilot import (
        GroundedCopilotConversation,
        GroundedCopilotMessage,
    )

    bind = op.get_bind()
    for model in (GroundedCopilotMessage, GroundedCopilotConversation):
        model.__table__.drop(bind=bind, checkfirst=True)
