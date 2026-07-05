"""Tamper-evident audit logging columns.

Revision ID: 0005_audit
Revises: 0004_scim
Create Date: 2026-06-29

Adds ``organization_id`` + hash-chain columns (``sequence``, ``entry_hash``,
``prev_hash``) to ``audit_logs``. Inspector-guarded so it is idempotent: a fresh
``alembic upgrade head`` already has these columns (the squashed
``0001_baseline`` builds the schema from live ORM metadata), while a database
stamped before this upgrade gets the columns added here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_audit"
down_revision: str | None = "0004_scim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = {
    "organization_id": sa.Column("organization_id", sa.String(36), nullable=True),
    "sequence": sa.Column("sequence", sa.Integer(), nullable=True),
    "entry_hash": sa.Column("entry_hash", sa.String(64), nullable=True),
    "prev_hash": sa.Column("prev_hash", sa.String(64), nullable=True),
}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = {c["name"] for c in insp.get_columns("audit_logs")}
    for name, column in _COLUMNS.items():
        if name not in existing:
            op.add_column("audit_logs", column)

    index_names = {ix["name"] for ix in insp.get_indexes("audit_logs")}
    if "ix_audit_logs_organization_id" not in index_names:
        op.create_index(
            "ix_audit_logs_organization_id", "audit_logs", ["organization_id"]
        )
    if "ix_audit_logs_sequence" not in index_names:
        op.create_index("ix_audit_logs_sequence", "audit_logs", ["sequence"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    index_names = {ix["name"] for ix in insp.get_indexes("audit_logs")}
    if "ix_audit_logs_sequence" in index_names:
        op.drop_index("ix_audit_logs_sequence", table_name="audit_logs")
    if "ix_audit_logs_organization_id" in index_names:
        op.drop_index("ix_audit_logs_organization_id", table_name="audit_logs")

    existing = {c["name"] for c in insp.get_columns("audit_logs")}
    for name in ("prev_hash", "entry_hash", "sequence", "organization_id"):
        if name in existing:
            op.drop_column("audit_logs", name)
