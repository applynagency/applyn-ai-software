"""Async job queue table (jobs).

Revision ID: 0002_jobs
Revises: 0001_baseline
Create Date: 2026-06-28

Adds the ``jobs`` table backing the Arq async job queue (status / progress /
retries / dead-letter / cancellation). Created directly from the ORM model so
the migration stays exactly in sync with ``app.models.job.Job``.

``checkfirst=True`` makes this idempotent: the squashed ``0001_baseline`` derives
its schema from the live ORM metadata (which now includes ``jobs``), so a fresh
``alembic upgrade head`` already created the table here — while a database that
was stamped at ``0001_baseline`` *before* the jobs model existed still gets it.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_jobs"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.models.job import Job

    Job.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from app.models.job import Job

    Job.__table__.drop(bind=op.get_bind(), checkfirst=True)
