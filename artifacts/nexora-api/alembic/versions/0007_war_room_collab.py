"""Collaborative war room: participants, attachments, evidence, approvals.

Revision ID: 0007_war_room_collab
Revises: 0006_grounded_copilot
Create Date: 2026-06-29

Adds the real-time collaboration surface to the war room:

* new collaboration columns on ``war_room_messages`` (author/user/thread/mentions)
* new tables ``war_room_participants``, ``war_room_attachments``,
  ``war_room_evidence``, ``war_room_approvals``

Inspector-guarded column adds + idempotent ORM ``create(checkfirst=True)`` table
creation, matching the project's migration conventions: a fresh
``alembic upgrade head`` already has everything (the squashed ``0001_baseline``
builds the schema from live ORM metadata), while a previously-stamped database
gets the new columns/tables here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_war_room_collab"
down_revision: str | None = "0006_grounded_copilot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MESSAGE_COLUMNS = {
    "author_type": sa.Column(
        "author_type", sa.String(20), nullable=False, server_default="AI"
    ),
    "user_id": sa.Column("user_id", sa.String(36), nullable=True),
    "user_name": sa.Column("user_name", sa.String(255), nullable=True),
    "parent_message_id": sa.Column("parent_message_id", sa.String(36), nullable=True),
    "mentions": sa.Column("mentions", sa.JSON(), nullable=True),
}


def upgrade() -> None:
    from app.models.war_room import (
        WarRoomApproval,
        WarRoomAttachment,
        WarRoomEvidence,
        WarRoomParticipant,
    )

    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing = {c["name"] for c in insp.get_columns("war_room_messages")}
    for name, column in _MESSAGE_COLUMNS.items():
        if name not in existing:
            op.add_column("war_room_messages", column)

    index_names = {ix["name"] for ix in insp.get_indexes("war_room_messages")}
    if "ix_war_room_messages_parent_message_id" not in index_names:
        op.create_index(
            "ix_war_room_messages_parent_message_id",
            "war_room_messages",
            ["parent_message_id"],
        )

    for model in (
        WarRoomParticipant,
        WarRoomAttachment,
        WarRoomEvidence,
        WarRoomApproval,
    ):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    from app.models.war_room import (
        WarRoomApproval,
        WarRoomAttachment,
        WarRoomEvidence,
        WarRoomParticipant,
    )

    bind = op.get_bind()
    insp = sa.inspect(bind)

    for model in (
        WarRoomApproval,
        WarRoomEvidence,
        WarRoomAttachment,
        WarRoomParticipant,
    ):
        model.__table__.drop(bind=bind, checkfirst=True)

    index_names = {ix["name"] for ix in insp.get_indexes("war_room_messages")}
    if "ix_war_room_messages_parent_message_id" in index_names:
        op.drop_index(
            "ix_war_room_messages_parent_message_id", table_name="war_room_messages"
        )

    existing = {c["name"] for c in insp.get_columns("war_room_messages")}
    for name in ("mentions", "parent_message_id", "user_name", "user_id", "author_type"):
        if name in existing:
            op.drop_column("war_room_messages", name)
