"""Enterprise SSO tables (sso_connections, sso_identities) + nullable password.

Revision ID: 0003_sso
Revises: 0002_jobs
Create Date: 2026-06-29

Adds the SSO connection/identity tables backing OIDC + SAML single sign-on, and
relaxes ``users.hashed_password`` to nullable so SSO-only (passwordless) users
can be JIT-provisioned.

Tables are created directly from the ORM models with ``checkfirst=True`` so the
migration stays in sync with ``app.models.sso`` and is idempotent (the squashed
``0001_baseline`` derives its schema from live ORM metadata, which now includes
these tables — a fresh ``alembic upgrade head`` already created them, while a DB
stamped before SSO existed still gets them here).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_sso"
down_revision: str | None = "0002_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.models.sso import SSOConnection, SSOIdentity

    bind = op.get_bind()
    SSOConnection.__table__.create(bind=bind, checkfirst=True)
    SSOIdentity.__table__.create(bind=bind, checkfirst=True)

    # Relax users.hashed_password to nullable for SSO-only accounts. Skipped on
    # SQLite (limited ALTER support; tests build the schema from ORM metadata
    # which is already nullable).
    if bind.dialect.name != "sqlite":
        op.alter_column(
            "users", "hashed_password", existing_type=sa.Text(), nullable=True
        )


def downgrade() -> None:
    from app.models.sso import SSOConnection, SSOIdentity

    bind = op.get_bind()
    SSOIdentity.__table__.drop(bind=bind, checkfirst=True)
    SSOConnection.__table__.drop(bind=bind, checkfirst=True)
