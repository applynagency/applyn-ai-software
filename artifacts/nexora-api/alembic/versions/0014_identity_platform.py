"""Enterprise identity & access platform (Sprint 61A).

Adds the net-new identity primitives:

* ``service_accounts`` — non-human organization principals.
* ``api_keys`` — hashed, prefix-addressable credentials (org / personal /
  service-account).
* ``user_sessions`` — database-backed sessions with refresh-token rotation.
* ``organization_security_policies`` — per-org configurable security controls.
* ``user_mfa_totp`` / ``mfa_recovery_codes`` — TOTP MFA + recovery codes.

Also extends ``sso_connections`` with single-logout, SAML certificate-rotation,
metadata-import and IdP-initiated columns.

Idempotent: guarded by the live inspector so it is safe to re-run and safe on
databases where parts already exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0014_identity_platform"
down_revision: str | None = "0013_converge_graph"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_column(insp, table: str, column: str) -> bool:
    if not _has_table(insp, table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # --- service_accounts ---------------------------------------------------
    if not _has_table(insp, "service_accounts"):
        op.create_table(
            "service_accounts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="VIEWER"),
            sa.Column("scopes", sa.JSON(), nullable=True),
            sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("organization_id", "name", name="uq_service_account_name"),
        )
        op.create_index(
            "ix_service_accounts_organization_id", "service_accounts", ["organization_id"]
        )

    # --- api_keys -----------------------------------------------------------
    if not _has_table(insp, "api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("principal_type", sa.String(length=20), nullable=False),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("service_account_id", sa.String(length=36), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("prefix", sa.String(length=24), nullable=False),
            sa.Column("hashed_key", sa.String(length=64), nullable=False),
            sa.Column("scopes", sa.JSON(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_ip", sa.String(length=45), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["service_account_id"], ["service_accounts.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("prefix", name="uq_api_key_prefix"),
            sa.UniqueConstraint("hashed_key", name="uq_api_key_hash"),
        )
        op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"])
        op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])
        op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
        op.create_index(
            "ix_api_keys_service_account_id", "api_keys", ["service_account_id"]
        )

    # --- user_sessions ------------------------------------------------------
    if not _has_table(insp, "user_sessions"):
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
            sa.Column("access_jti", sa.String(length=64), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("device_label", sa.String(length=255), nullable=True),
            sa.Column("rotation_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_reason", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="SET NULL"
            ),
        )
        op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
        op.create_index(
            "ix_user_sessions_organization_id", "user_sessions", ["organization_id"]
        )
        op.create_index(
            "ix_user_sessions_refresh_token_hash",
            "user_sessions",
            ["refresh_token_hash"],
        )
        op.create_index("ix_user_sessions_access_jti", "user_sessions", ["access_jti"])
        op.create_index("ix_user_sessions_revoked_at", "user_sessions", ["revoked_at"])

    # --- organization_security_policies -------------------------------------
    if not _has_table(insp, "organization_security_policies"):
        op.create_table(
            "organization_security_policies",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("password_min_length", sa.Integer(), nullable=False, server_default="12"),
            sa.Column("password_require_uppercase", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("password_require_lowercase", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("password_require_number", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("password_require_symbol", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("session_timeout_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_concurrent_sessions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("allowed_email_domains", sa.JSON(), nullable=True),
            sa.Column("ip_allowlist", sa.JSON(), nullable=True),
            sa.Column("api_keys_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("api_key_max_age_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint(
                "organization_id", name="uq_org_security_policy_org"
            ),
        )
        op.create_index(
            "ix_org_security_policies_org",
            "organization_security_policies",
            ["organization_id"],
        )

    # --- user_mfa_totp ------------------------------------------------------
    if not _has_table(insp, "user_mfa_totp"):
        op.create_table(
            "user_mfa_totp",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("encrypted_secret", sa.Text(), nullable=False),
            sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", name="uq_user_mfa_totp_user"),
        )
        op.create_index("ix_user_mfa_totp_user_id", "user_mfa_totp", ["user_id"])

    # --- mfa_recovery_codes -------------------------------------------------
    if not _has_table(insp, "mfa_recovery_codes"):
        op.create_table(
            "mfa_recovery_codes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"]
        )
        op.create_index(
            "ix_mfa_recovery_codes_code_hash", "mfa_recovery_codes", ["code_hash"]
        )

    # --- sso_connections extensions -----------------------------------------
    for column, coltype, default in (
        ("logout_url", sa.String(length=512), None),
        ("idp_x509_cert_next", sa.Text(), None),
        ("idp_metadata_xml", sa.Text(), None),
        ("allow_idp_initiated", sa.Boolean(), sa.true()),
    ):
        if _has_table(insp, "sso_connections") and not _has_column(
            insp, "sso_connections", column
        ):
            kwargs = {"nullable": True}
            if default is not None:
                kwargs["server_default"] = default
                kwargs["nullable"] = False
            op.add_column("sso_connections", sa.Column(column, coltype, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    for column in (
        "allow_idp_initiated",
        "idp_metadata_xml",
        "idp_x509_cert_next",
        "logout_url",
    ):
        if _has_column(insp, "sso_connections", column):
            op.drop_column("sso_connections", column)

    for table in (
        "mfa_recovery_codes",
        "user_mfa_totp",
        "organization_security_policies",
        "user_sessions",
        "api_keys",
        "service_accounts",
    ):
        if _has_table(insp, table):
            op.drop_table(table)
