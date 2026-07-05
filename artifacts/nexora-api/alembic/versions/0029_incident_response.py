"""Alembic migration for Enterprise Incident Response Platform (Sprint 65C)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0029_incident_response"
down_revision: str | None = "0028_observability_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = [
        ("ir_schedule_overrides", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("schedule_id", sa.String(36), sa.ForeignKey("oncall_schedules.id", ondelete="CASCADE"), nullable=False),
            sa.Column("replacement_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reason", sa.String(255), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_status_pages", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("slug", sa.String(120), nullable=False),
            sa.Column("visibility", sa.String(20), nullable=False, server_default="PUBLIC"),
            sa.Column("branding", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_status_components", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("page_id", sa.String(36), sa.ForeignKey("ir_status_pages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="OPERATIONAL"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_status_incidents", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("page_id", sa.String(36), sa.ForeignKey("ir_status_pages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("incident_id", sa.String(36), nullable=True),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="INVESTIGATING"),
            sa.Column("impact", sa.String(30), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updates", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_status_subscribers", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("page_id", sa.String(36), sa.ForeignKey("ir_status_pages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_communication_templates", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("subject", sa.String(500), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("locale", sa.String(10), nullable=False, server_default="en"),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_communications", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("incident_id", sa.String(36), nullable=True),
            sa.Column("template_id", sa.String(36), nullable=True),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("subject", sa.String(500), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_major_incidents", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("incident_id", sa.String(36), nullable=False, unique=True),
            sa.Column("war_room_id", sa.String(36), nullable=True),
            sa.Column("roles", sa.JSON(), nullable=False),
            sa.Column("stakeholders", sa.JSON(), nullable=False),
            sa.Column("decision_log", sa.JSON(), nullable=False),
            sa.Column("executive_bridge", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ir_coordinator_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("incident_id", sa.String(36), nullable=True),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in tables:
        if name not in insp.get_table_names():
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])


def downgrade() -> None:
    for name in (
        "ir_coordinator_runs", "ir_major_incidents", "ir_communications",
        "ir_communication_templates", "ir_status_subscribers", "ir_status_incidents",
        "ir_status_components", "ir_status_pages", "ir_schedule_overrides",
    ):
        op.drop_table(name)
