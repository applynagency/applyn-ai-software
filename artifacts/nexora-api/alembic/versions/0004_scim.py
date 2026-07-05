"""SCIM 2.0 provisioning tables.

Revision ID: 0004_scim
Revises: 0003_sso
Create Date: 2026-06-29

Adds the SCIM resource tables (scim_tokens, scim_users, scim_groups,
scim_group_members) backing automated user/group provisioning from an IdP.

Created directly from the ORM models with ``checkfirst=True`` so the migration
stays in sync with ``app.models.scim`` and is idempotent (the squashed
``0001_baseline`` derives its schema from live ORM metadata, which now includes
these tables — a fresh ``alembic upgrade head`` already created them, while a DB
stamped before SCIM existed still gets them here).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_scim"
down_revision: str | None = "0003_sso"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.models.scim import ScimGroup, ScimGroupMember, ScimToken, ScimUser

    bind = op.get_bind()
    for model in (ScimToken, ScimUser, ScimGroup, ScimGroupMember):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    from app.models.scim import ScimGroup, ScimGroupMember, ScimToken, ScimUser

    bind = op.get_bind()
    for model in (ScimGroupMember, ScimGroup, ScimUser, ScimToken):
        model.__table__.drop(bind=bind, checkfirst=True)
