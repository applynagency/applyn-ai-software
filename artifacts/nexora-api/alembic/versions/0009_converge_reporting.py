"""Reporting convergence: retire Leadership Reports (Executive is canonical).

Revision ID: 0009_converge_reporting
Revises: 0008_hardening_indexes
Create Date: 2026-06-30

Sprint 60B architecture convergence. The Leadership Reports product is removed;
the Executive Report service is the single reporting engine. This migration drops
the now-orphaned Leadership tables on previously-stamped databases. Fresh
``alembic upgrade head`` never created them (their ORM models are deleted, so the
squashed baseline no longer builds them). Inspector-guarded + idempotent.

Irreversible: the Leadership ORM models no longer exist, so ``downgrade`` cannot
recreate the tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_converge_reporting"
down_revision: str | None = "0008_hardening_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_TABLES = ("leadership_report_schedules", "leadership_reports")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())
    for table in _DROP_TABLES:
        if table in existing:
            op.drop_table(table)


def downgrade() -> None:  # pragma: no cover - irreversible convergence
    raise NotImplementedError(
        "Leadership Reports were permanently retired in 0009_converge_reporting."
    )
