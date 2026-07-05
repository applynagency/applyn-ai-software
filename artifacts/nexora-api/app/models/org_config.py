"""Organization-scoped configuration variables (secrets and non-secrets)."""

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class OrgConfigVariable(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "org_config_variables"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", "environment", name="uq_org_config_key_env"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), nullable=False, default="default")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    value_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
