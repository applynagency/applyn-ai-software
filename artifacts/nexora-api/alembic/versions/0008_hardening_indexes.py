"""Hardening: atomic alert dedup, war-room sequence uniqueness, hot-path indexes.

Revision ID: 0008_hardening_indexes
Revises: 0007_war_room_collab
Create Date: 2026-06-30

Forward DDL for the architecture-hardening sprint. A fresh ``alembic upgrade
head`` already has everything (the squashed ``0001_baseline`` builds the schema
from live ORM metadata); this migration brings *previously-stamped* databases up
to date:

* ``monitoring_alerts.dedup_key`` + partial-unique index
  ``uq_monitoring_alerts_active_dedup`` (status='FIRING') — makes alert dedup
  atomic so concurrent ingests cannot create duplicates.
* ``uq_war_room_messages_seq`` unique constraint on (war_room_id, sequence) —
  prevents duplicate message sequence numbers.
* composite list-path indexes on ``monitoring_alerts``,
  ``incident_investigations`` and ``workflow_executions``.

All steps are inspector-guarded and idempotent. The partial-unique index is only
created on PostgreSQL (sqlite test DBs build it from ORM metadata).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_hardening_indexes"
down_revision: str | None = "0007_war_room_collab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(insp, table: str) -> set[str]:
    try:
        return {ix["name"] for ix in insp.get_indexes(table)}
    except Exception:  # pragma: no cover - table may not exist on partial DBs
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    # 1) monitoring_alerts.dedup_key + atomic-dedup partial unique index
    ma_cols = {c["name"] for c in insp.get_columns("monitoring_alerts")}
    if "dedup_key" not in ma_cols:
        op.add_column(
            "monitoring_alerts", sa.Column("dedup_key", sa.String(64), nullable=True)
        )
    ma_idx = _index_names(insp, "monitoring_alerts")
    if "uq_monitoring_alerts_active_dedup" not in ma_idx:
        if dialect == "postgresql":
            op.create_index(
                "uq_monitoring_alerts_active_dedup",
                "monitoring_alerts",
                ["organization_id", "dedup_key"],
                unique=True,
                postgresql_where=sa.text("status = 'FIRING' AND dedup_key IS NOT NULL"),
            )
        elif dialect == "sqlite":
            op.create_index(
                "uq_monitoring_alerts_active_dedup",
                "monitoring_alerts",
                ["organization_id", "dedup_key"],
                unique=True,
                sqlite_where=sa.text("status = 'FIRING' AND dedup_key IS NOT NULL"),
            )
    if "ix_monitoring_alerts_org_status_created" not in ma_idx:
        op.create_index(
            "ix_monitoring_alerts_org_status_created",
            "monitoring_alerts",
            ["organization_id", "status", "created_at"],
        )

    # 2) war_room_messages unique (war_room_id, sequence)
    wrm_idx = _index_names(insp, "war_room_messages")
    wrm_uqs = {
        uc.get("name") for uc in insp.get_unique_constraints("war_room_messages")
    }
    if "uq_war_room_messages_seq" not in (wrm_idx | wrm_uqs):
        if dialect == "postgresql":
            op.create_unique_constraint(
                "uq_war_room_messages_seq",
                "war_room_messages",
                ["war_room_id", "sequence"],
            )
        elif dialect == "sqlite":
            op.create_index(
                "uq_war_room_messages_seq",
                "war_room_messages",
                ["war_room_id", "sequence"],
                unique=True,
            )

    # 3) composite hot-path indexes
    ii_idx = _index_names(insp, "incident_investigations")
    if "ix_incident_investigations_org_status_created" not in ii_idx:
        op.create_index(
            "ix_incident_investigations_org_status_created",
            "incident_investigations",
            ["organization_id", "status", "created_at"],
        )
    we_idx = _index_names(insp, "workflow_executions")
    if "ix_workflow_executions_org_status_created" not in we_idx:
        op.create_index(
            "ix_workflow_executions_org_status_created",
            "workflow_executions",
            ["organization_id", "status", "created_at"],
        )
    if "ix_workflow_executions_org_workflow_created" not in we_idx:
        op.create_index(
            "ix_workflow_executions_org_workflow_created",
            "workflow_executions",
            ["organization_id", "workflow_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    for name, table in (
        ("ix_workflow_executions_org_workflow_created", "workflow_executions"),
        ("ix_workflow_executions_org_status_created", "workflow_executions"),
        ("ix_incident_investigations_org_status_created", "incident_investigations"),
        ("ix_monitoring_alerts_org_status_created", "monitoring_alerts"),
        ("uq_monitoring_alerts_active_dedup", "monitoring_alerts"),
    ):
        if name in _index_names(insp, table):
            op.drop_index(name, table_name=table)

    wrm_uqs = {
        uc.get("name") for uc in insp.get_unique_constraints("war_room_messages")
    }
    if "uq_war_room_messages_seq" in wrm_uqs and dialect == "postgresql":
        op.drop_constraint(
            "uq_war_room_messages_seq", "war_room_messages", type_="unique"
        )
    elif "uq_war_room_messages_seq" in _index_names(insp, "war_room_messages"):
        op.drop_index("uq_war_room_messages_seq", table_name="war_room_messages")

    ma_cols = {c["name"] for c in insp.get_columns("monitoring_alerts")}
    if "dedup_key" in ma_cols:
        op.drop_column("monitoring_alerts", "dedup_key")
