"""Schemas for SCIM admin token management.

SCIM resource payloads (Users/Groups/PATCH/Bulk) are handled as raw SCIM JSON;
only the admin token-management endpoints use typed request/response models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScimTokenCreate(BaseModel):
    organization_id: str
    name: str = Field(min_length=1, max_length=255)


class ScimTokenResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    token_prefix: str
    active: bool

    model_config = {"from_attributes": True}


class ScimTokenCreatedResponse(ScimTokenResponse):
    # Plaintext bearer token — shown exactly once, never stored.
    token: str


class ScimTokenListResponse(BaseModel):
    tokens: list[ScimTokenResponse]
    total: int
