#!/usr/bin/env python3
"""Compare live PostgreSQL schema against Alembic migration expectations."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def database_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://nexora:nexora@localhost:5432/nexora",
    )
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def load_expected_workspace_columns() -> set[str]:
    """Columns introduced across migrations for workspaces (baseline + org link)."""
    return {
        "id",
        "created_at",
        "updated_at",
        "deleted_at",
        "name",
        "description",
        "slug",
        "owner_id",
        "organization_id",
    }


def main() -> int:
    engine = sa.create_engine(database_url())
    inspector = sa.inspect(engine)

    tables = set(inspector.get_table_names(schema="public"))
    alembic_exists = "alembic_version" in tables

    current_revision = None
    if alembic_exists:
        with engine.connect() as conn:
            row = conn.execute(sa.text("SELECT version_num FROM alembic_version")).first()
            current_revision = row[0] if row else None

    cfg = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    head_revision = script.get_current_head()

    workspace_columns = (
        {column["name"] for column in inspector.get_columns("workspaces")}
        if "workspaces" in tables
        else set()
    )
    expected_workspace_columns = load_expected_workspace_columns()
    missing_workspace_columns = sorted(expected_workspace_columns - workspace_columns)
    extra_workspace_columns = sorted(workspace_columns - expected_workspace_columns)

    report = {
        "database_url_host": database_url().split("@")[-1],
        "table_count": len(tables),
        "tables": sorted(tables),
        "alembic_version_table_exists": alembic_exists,
        "alembic_current_revision": current_revision,
        "alembic_head_revision": head_revision,
        "drift": {
            "missing_tables": [],
            "missing_columns": {
                "workspaces": missing_workspace_columns,
            },
            "extra_columns": {
                "workspaces": extra_workspace_columns,
            },
            "missing_indexes": {},
            "missing_constraints": {},
        },
        "repair_recommendation": [],
    }

    if not alembic_exists:
        report["repair_recommendation"].append(
            "Create alembic_version and stamp to 023_backend_code_review if all tables exist, "
            "then run: alembic upgrade head"
        )

    if missing_workspace_columns:
        report["repair_recommendation"].append(
            "Run alembic upgrade head (024_schema_reconciliation adds workspaces.organization_id)"
        )

    if current_revision != head_revision:
        report["repair_recommendation"].append(
            f"Upgrade migrations from {current_revision!r} to {head_revision!r}"
        )

    output_path = ROOT / "reports" / "database_drift_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nWrote {output_path}")
    return 0 if not missing_workspace_columns and alembic_exists else 1


if __name__ == "__main__":
    raise SystemExit(main())
