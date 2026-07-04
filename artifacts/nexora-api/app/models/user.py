from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable: SSO-only users (provisioned via OIDC/SAML) have no local password.
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspaces: Mapped[list["Workspace"]] = relationship(  # noqa: F821
        "Workspace", back_populates="owner", lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        "AuditLog", back_populates="user", lazy="selectin"
    )
    organization_memberships: Mapped[list["OrganizationMember"]] = relationship(  # noqa: F821
        "OrganizationMember", back_populates="user", lazy="selectin"
    )
