"""Baseline schema (squash of legacy migrations 001-076).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-28

This single baseline replaces the 76 legacy incremental migrations (archived in
``alembic/legacy_versions/``). It materializes the *entire* current schema from
the ORM models, which is the authoritative source of truth.

Why metadata create_all instead of hand-written DDL?
  * The legacy migrations never built a database from scratch (no migration ever
    created the foundational ``users``/``workspaces`` tables, and several
    re-emitted ``CREATE TYPE`` for shared enums). The runtime ``create_all()``
    (now removed) masked this.
  * Driving the baseline from ``Base.metadata`` guarantees the migrated schema
    matches the models exactly, resolves FK ordering, and creates each shared
    enum exactly once.

Existing databases whose schema was built by the old runtime ``create_all()``
must be stamped to this revision instead of re-run:

    alembic stamp 0001_baseline

Fresh databases simply run:

    alembic upgrade head
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    import app.models  # noqa: F401 — registers every ORM model
    from app.database.base import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    import app.models  # noqa: F401
    from app.database.base import Base

    Base.metadata.drop_all(bind=op.get_bind())
