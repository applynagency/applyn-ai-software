"""Discovery convergence: one discovery system (Universal Discovery).

Revision ID: 0012_converge_discovery
Revises: 0011_converge_copilot
Create Date: 2026-06-30

Sprint 60B architecture convergence. The legacy infrastructure-discovery system
(``InfrastructureDiscoveryService`` / ``DiscoveryPipelineService`` writing
``infrastructure_discoveries`` + ``discovery_resources`` + ``discovery_change_events``)
is replaced by the single Universal Discovery engine whose inventory is
``discovered_assets`` and whose graph is ``knowledge_graph_nodes`` /
``knowledge_graph_edges``.

This migration, on previously-stamped databases:

1. migrates every ``discovery_resources`` row into the unified ``discovered_assets``
   inventory (domain = INFRASTRUCTURE), **preserving the primary key** so existing
   references stay stable, and is idempotent (rows already migrated are skipped);
2. detaches the legacy ``discovery_scan_runs.discovery_id`` foreign key (it pointed
   at ``infrastructure_discoveries``, which is being dropped);
3. drops the obsolete legacy tables.

The service-to-service dependency graph (``service_dependencies``) is the single
retained dependency graph and is intentionally NOT dropped. The Platform
Knowledge Graph is rebuilt from the inventory on the next discovery scan.

Fresh ``alembic upgrade head`` never created the legacy tables (their ORM models
are deleted), so every step is inspector-guarded and safe to re-run.

Irreversible: the legacy discovery ORM models no longer exist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_converge_discovery"
down_revision: str | None = "0011_converge_copilot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_TABLES = (
    "discovery_change_events",
    "discovery_resources",
    "infrastructure_discoveries",
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # 1. Migrate legacy DiscoveryResource rows into the unified inventory.
    if "discovery_resources" in tables and "discovered_assets" in tables:
        meta = sa.MetaData()
        src = sa.Table("discovery_resources", meta, autoload_with=bind)
        dst = sa.Table("discovered_assets", meta, autoload_with=bind)
        dst_cols = set(dst.c.keys())
        existing_ids = set(bind.execute(sa.select(dst.c.id)).scalars().all())

        to_insert: list[dict] = []
        for r in bind.execute(sa.select(src)).mappings().all():
            if r["id"] in existing_ids:
                continue  # idempotent — already migrated
            md = r.get("resource_metadata")
            md = dict(md) if isinstance(md, dict) else {}
            if r.get("service_name"):
                md["service_name"] = r["service_name"]
            name = r.get("name") or r.get("identifier") or r["id"]
            payload = {
                "id": r["id"],
                "organization_id": r["organization_id"],
                "provider": r["provider"],
                "domain": "INFRASTRUCTURE",
                "resource_type": r["resource_type"],
                "resource_id": r.get("identifier") or name,
                "resource_name": name,
                "display_name": r.get("name"),
                "environment": r.get("environment"),
                "health": "UNKNOWN",
                "tags": {},
                "relationships": [],
                "asset_metadata": md,
                "first_seen_at": r.get("created_at"),
                "last_seen_at": r.get("updated_at") or r.get("created_at"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
            }
            to_insert.append({k: v for k, v in payload.items() if k in dst_cols})

        if to_insert:
            bind.execute(dst.insert(), to_insert)

    # 2. Detach the legacy FK column on discovery_scan_runs so the referenced
    #    table can be dropped (and remove the now-meaningless link).
    if "discovery_scan_runs" in tables:
        cols = {c["name"] for c in insp.get_columns("discovery_scan_runs")}
        if "discovery_id" in cols:
            with op.batch_alter_table("discovery_scan_runs") as batch:
                batch.drop_column("discovery_id")

    # 3. Drop obsolete legacy discovery tables.
    for table in _DROP_TABLES:
        if table in tables:
            op.drop_table(table)


def downgrade() -> None:  # pragma: no cover - irreversible convergence
    raise NotImplementedError(
        "Legacy infrastructure discovery was permanently retired in "
        "0012_converge_discovery."
    )
