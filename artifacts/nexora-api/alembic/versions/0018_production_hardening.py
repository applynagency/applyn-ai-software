"""Enterprise production hardening & scale (Sprint 62B).

Additive, idempotent schema changes that support production hardening:

* ``jobs``           — execution leases (lease_owner/lease_expires_at/heartbeat_at),
                       per-run timeout + scheduling priority + recovery index
* ``domain_events``  — idempotency_key (exactly-once / idempotent replication) +
                       consumed_at (durable leader-elected consumer)
* ``search_documents`` — incremental search index (no full rebuilds)
* ``search_query_logs`` — search analytics

Plus production-tuning indexes (covering/partial) for the hottest query paths.
Guarded by the live inspector so it is safe to re-run.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0018_production_hardening"
down_revision: str | None = "0017_platform_convergence"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_column(insp, table: str, column: str) -> bool:
    if not _has_table(insp, table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def _has_index(insp, table: str, name: str) -> bool:
    if not _has_table(insp, table):
        return False
    return name in {ix["name"] for ix in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # --- jobs: execution leases + priority + timeout -----------------------
    if _has_table(insp, "jobs"):
        if not _has_column(insp, "jobs", "priority"):
            op.add_column("jobs", sa.Column(
                "priority", sa.String(length=10), nullable=False, server_default="default"))
        if not _has_column(insp, "jobs", "lease_owner"):
            op.add_column("jobs", sa.Column("lease_owner", sa.String(length=64), nullable=True))
        if not _has_column(insp, "jobs", "lease_expires_at"):
            op.add_column("jobs", sa.Column(
                "lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(insp, "jobs", "heartbeat_at"):
            op.add_column("jobs", sa.Column(
                "heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(insp, "jobs", "timeout_seconds"):
            op.add_column("jobs", sa.Column("timeout_seconds", sa.Integer(), nullable=True))
        if not _has_index(insp, "jobs", "ix_jobs_status_lease"):
            op.create_index("ix_jobs_status_lease", "jobs", ["status", "lease_expires_at"])
        if not _has_index(insp, "jobs", "ix_jobs_org_status_created"):
            op.create_index("ix_jobs_org_status_created", "jobs",
                            ["organization_id", "status", "created_at"])
        if not _has_index(insp, "jobs", "ix_jobs_priority"):
            op.create_index("ix_jobs_priority", "jobs", ["priority"])

    # --- domain_events: exactly-once + durable consumer --------------------
    if _has_table(insp, "domain_events"):
        if not _has_column(insp, "domain_events", "idempotency_key"):
            op.add_column("domain_events", sa.Column(
                "idempotency_key", sa.String(length=120), nullable=True))
            op.create_index("uq_domain_events_idempotency", "domain_events",
                            ["idempotency_key"], unique=True)
        if not _has_column(insp, "domain_events", "consumed_at"):
            op.add_column("domain_events", sa.Column(
                "consumed_at", sa.DateTime(timezone=True), nullable=True))

    # --- search_documents (incremental index) ------------------------------
    if not _has_table(insp, "search_documents"):
        op.create_table(
            "search_documents",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("entity_type", sa.String(length=40), nullable=False),
            sa.Column("entity_id", sa.String(length=64), nullable=False),
            sa.Column("title", sa.Text(), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("keywords", sa.Text(), nullable=False, server_default=""),
            sa.Column("url", sa.String(length=500), nullable=True),
            sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("entity_type", "entity_id", name="uq_search_doc_entity"),
        )
        op.create_index("ix_search_documents_org_type", "search_documents",
                        ["organization_id", "entity_type"])

    # --- search_query_logs (analytics) -------------------------------------
    if not _has_table(insp, "search_query_logs"):
        op.create_table(
            "search_query_logs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("query", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("normalized_query", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("results_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("took_ms", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("profile", sa.String(length=40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_search_query_logs_org_created", "search_query_logs",
                        ["organization_id", "created_at"])
        op.create_index("ix_search_query_logs_norm", "search_query_logs", ["normalized_query"])

    # --- production-tuning indexes on hot paths -----------------------------
    if not _has_index(insp, "domain_events", "ix_domain_events_org_status_created"):
        op.create_index("ix_domain_events_org_status_created", "domain_events",
                        ["organization_id", "status", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    for table in ("search_query_logs", "search_documents"):
        if _has_table(insp, table):
            op.drop_table(table)

    if _has_index(insp, "domain_events", "ix_domain_events_org_status_created"):
        op.drop_index("ix_domain_events_org_status_created", table_name="domain_events")
    if _has_column(insp, "domain_events", "consumed_at"):
        op.drop_column("domain_events", "consumed_at")
    # idempotency_key carries a UNIQUE constraint that SQLite stores inline on the
    # table, so drop it inside a batch (table-recreate) to also remove the
    # constraint. On Postgres the constraint is dropped with the column.
    if _has_column(insp, "domain_events", "idempotency_key"):
        with op.batch_alter_table("domain_events") as batch:
            try:
                batch.drop_constraint("uq_domain_events_idempotency", type_="unique")
            except Exception:
                pass
            batch.drop_column("idempotency_key")

    for ix in ("ix_jobs_priority", "ix_jobs_org_status_created", "ix_jobs_status_lease"):
        if _has_index(insp, "jobs", ix):
            op.drop_index(ix, table_name="jobs")
    for col in ("timeout_seconds", "heartbeat_at", "lease_expires_at",
                "lease_owner", "priority"):
        if _has_column(insp, "jobs", col):
            op.drop_column("jobs", col)
