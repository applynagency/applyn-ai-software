from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.organization import InvitationStatus, OrganizationRole
from app.repositories.organization import slugify


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    description: str | None = None

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return slugify(value)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationContextToken(BaseModel):
    """Sprint 54B.1 — org-scoped tokens issued automatically on first org create."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    organization_id: str
    role: OrganizationRole


class OrganizationCreatedResponse(OrganizationResponse):
    """Sprint 54B.1 — create response carries auto-switch context for the first org.

    When a user creates their **first** organization the API auto-switches into
    it and returns an org-scoped token bundle, so no manual ``/switch`` call is
    required before using org-scoped endpoints.
    """

    auto_switched: bool = False
    context: OrganizationContextToken | None = None


class OrganizationListItemResponse(OrganizationResponse):
    """Organization summary for the current user's membership list."""

    role: OrganizationRole


class OrganizationListResponse(BaseModel):
    items: list[OrganizationListItemResponse]
    total: int


class OrganizationMemberCreate(BaseModel):
    user_id: str
    role: OrganizationRole = OrganizationRole.DEVELOPER


class OrganizationMemberResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: OrganizationRole
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationMemberListResponse(BaseModel):
    items: list[OrganizationMemberResponse]
    total: int


class InvitationCreate(BaseModel):
    organization_id: str
    email: EmailStr
    role: OrganizationRole = OrganizationRole.DEVELOPER


class InvitationAccept(BaseModel):
    token: str


class InvitationResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    role: OrganizationRole
    token: str
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitationListResponse(BaseModel):
    items: list[InvitationResponse]
    total: int


class InvitationPreviewResponse(BaseModel):
    organization_name: str
    email: str
    role: OrganizationRole
    valid: bool


class OrganizationSwitchResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    organization_id: str
    role: OrganizationRole
