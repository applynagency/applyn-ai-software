import re
from datetime import datetime

from pydantic import BaseModel, model_validator


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None
    slug: str | None = None

    @model_validator(mode="after")
    def set_slug(self) -> "WorkspaceCreate":
        if not self.slug:
            self.slug = re.sub(r"[^a-z0-9-]+", "-", self.name.lower()).strip("-")
        else:
            self.slug = re.sub(r"[^a-z0-9-]+", "-", self.slug.lower()).strip("-")
        return self


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str | None
    slug: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int
