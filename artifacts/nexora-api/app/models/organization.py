import enum
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class OrganizationRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    PROJECT_MANAGER = "PROJECT_MANAGER"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list["OrganizationInvitation"]] = relationship(
        "OrganizationInvitation",
        back_populates="organization",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    workspaces: Mapped[list["Workspace"]] = relationship(  # noqa: F821
        "Workspace", back_populates="organization", lazy="selectin"
    )


class OrganizationMember(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[OrganizationRole] = mapped_column(
        SAEnum(OrganizationRole), nullable=False, default=OrganizationRole.DEVELOPER
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="organization_memberships")  # noqa: F821


class OrganizationInvitation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organization_invitations"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[OrganizationRole] = mapped_column(SAEnum(OrganizationRole), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    invited_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="invitations")

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def default_expiry(days: int = 7) -> datetime:
        return datetime.now(UTC) + timedelta(days=days)

    def is_valid(self) -> bool:
        now = datetime.now(UTC)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return self.status == InvitationStatus.PENDING and expires_at > now
