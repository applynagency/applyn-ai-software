"""Onboarding convergence: retire the separate Infrastructure Onboarding wizard.

Revision ID: 0010_converge_onboarding
Revises: 0009_converge_reporting
Create Date: 2026-06-30

Sprint 60B architecture convergence. The infrastructure onboarding wizard is
removed; the single Guided Setup Wizard (``onboarding_sessions``) is the only
onboarding experience, and now auto-provisions the default SRE team + exposes the
sample-incident action that previously lived in the infra wizard. This migration
drops the orphaned infra-onboarding tables on previously-stamped databases.
Fresh ``alembic upgrade head`` never created them (their ORM models are deleted).
Inspector-guarded + idempotent.

Irreversible: the infra-onboarding ORM models no longer exist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_converge_onboarding"
down_revision: str | None = "0009_converge_reporting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_TABLES = ("wizard_provider_connections", "infra_onboarding_wizards")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())
    for table in _DROP_TABLES:
        if table in existing:
            op.drop_table(table)


def downgrade() -> None:  # pragma: no cover - irreversible convergence
    raise NotImplementedError(
        "Infrastructure Onboarding was permanently retired in 0010_converge_onboarding."
    )
