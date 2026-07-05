"""Copilot convergence: one unified Copilot (/v1/copilot).

Revision ID: 0011_converge_copilot
Revises: 0010_converge_onboarding
Create Date: 2026-06-30

Sprint 60B architecture convergence. The Reliability Copilot and SRE Copilot
standalone surfaces were merged into the single Grounded Copilot exposed at
``/v1/copilot`` (tables ``copilot_conversations`` / ``copilot_messages``). The
deterministic reliability/SRE retrieval engine is retained internally (no
persistence of its own). This migration drops the orphaned per-copilot session
tables on previously-stamped databases. Fresh ``alembic upgrade head`` never
created them (their ORM models are deleted). Inspector-guarded + idempotent.

Irreversible: the Reliability/SRE Copilot ORM models no longer exist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_converge_copilot"
down_revision: str | None = "0010_converge_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_TABLES = (
    "reliability_copilot_messages",
    "reliability_copilot_sessions",
    "sre_copilot_messages",
    "sre_copilot_sessions",
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())
    for table in _DROP_TABLES:
        if table in existing:
            op.drop_table(table)


def downgrade() -> None:  # pragma: no cover - irreversible convergence
    raise NotImplementedError(
        "Reliability/SRE Copilots were permanently retired in 0011_converge_copilot."
    )
