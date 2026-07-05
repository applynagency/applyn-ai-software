"""Graph platform unification: one graph (the Platform Knowledge Graph).

Revision ID: 0013_converge_graph
Revises: 0012_converge_discovery
Create Date: 2026-06-30

Sprint 60D graph convergence. The legacy service-dependency graph
(``service_dependencies`` consumed by a bespoke in-memory traversal engine) is
replaced by the single Platform Knowledge Graph (``knowledge_graph_nodes`` /
``knowledge_graph_edges``) owned by Universal Discovery. Service-topology edges
now live in the knowledge graph keyed by ``service:<id>`` node keys, with the
dependency type carried on ``relationship_type``.

This migration, on previously-stamped databases:

1. ensures a ``SERVICE`` knowledge-graph node exists for every service referenced
   by a dependency (``node_key = "service:<service_id>"``), naming it from the
   ``services`` catalog;
2. migrates every ``service_dependencies`` row into ``knowledge_graph_edges``,
   **preserving the primary key** so existing references stay stable;
3. drops the obsolete ``service_dependencies`` table.

Fresh ``alembic upgrade head`` never created ``service_dependencies`` (its ORM
model is deleted), so every step is inspector-guarded and safe to re-run
(already-migrated edges/nodes are skipped).

Irreversible: the legacy service-dependency ORM model no longer exists.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_converge_graph"
down_revision: str | None = "0012_converge_discovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SERVICE_PREFIX = "service:"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if (
        "service_dependencies" in tables
        and "knowledge_graph_edges" in tables
        and "knowledge_graph_nodes" in tables
    ):
        meta = sa.MetaData()
        src = sa.Table("service_dependencies", meta, autoload_with=bind)
        edges = sa.Table("knowledge_graph_edges", meta, autoload_with=bind)
        nodes = sa.Table("knowledge_graph_nodes", meta, autoload_with=bind)
        edge_cols = set(edges.c.keys())
        node_cols = set(nodes.c.keys())

        existing_edge_ids = set(bind.execute(sa.select(edges.c.id)).scalars().all())
        existing_node_keys = {
            (row[0], row[1])
            for row in bind.execute(
                sa.select(nodes.c.organization_id, nodes.c.node_key)
            ).all()
        }

        svc_names: dict[str, str] = {}
        if "services" in tables:
            svc = sa.Table("services", meta, autoload_with=bind)
            for row in bind.execute(sa.select(svc.c.id, svc.c.name)).all():
                svc_names[row[0]] = row[1]

        node_rows: list[dict] = []
        edge_rows: list[dict] = []
        seen_node_keys: set[tuple[str, str]] = set()

        for r in bind.execute(sa.select(src)).mappings().all():
            org = r["organization_id"]
            for sid in (r["source_service_id"], r["target_service_id"]):
                key = f"{_SERVICE_PREFIX}{sid}"
                if (org, key) in existing_node_keys or (org, key) in seen_node_keys:
                    continue
                seen_node_keys.add((org, key))
                payload = {
                    "id": str(uuid.uuid4()),
                    "organization_id": org,
                    "node_key": key,
                    "node_type": "SERVICE",
                    "name": svc_names.get(sid, sid),
                    "node_metadata": {"origin": "catalog"},
                    "last_seen_at": r.get("updated_at") or r.get("created_at"),
                    "created_at": r.get("created_at"),
                    "updated_at": r.get("updated_at"),
                }
                node_rows.append({k: v for k, v in payload.items() if k in node_cols})

            if r["id"] in existing_edge_ids:
                continue  # idempotent — edge already migrated
            dtype = r.get("dependency_type") or "SYNC"
            payload = {
                "id": r["id"],
                "organization_id": org,
                "source_key": f"{_SERVICE_PREFIX}{r['source_service_id']}",
                "target_key": f"{_SERVICE_PREFIX}{r['target_service_id']}",
                "relationship_type": dtype,
                "edge_metadata": {"dependency_type": dtype, "origin": "catalog"},
                "last_seen_at": r.get("updated_at") or r.get("created_at"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
            }
            edge_rows.append({k: v for k, v in payload.items() if k in edge_cols})

        if node_rows:
            bind.execute(nodes.insert(), node_rows)
        if edge_rows:
            bind.execute(edges.insert(), edge_rows)

    if "service_dependencies" in tables:
        op.drop_table("service_dependencies")


def downgrade() -> None:  # pragma: no cover - irreversible convergence
    raise NotImplementedError(
        "The legacy service-dependency graph was permanently retired in "
        "0013_converge_graph; topology now lives in the Platform Knowledge Graph."
    )
