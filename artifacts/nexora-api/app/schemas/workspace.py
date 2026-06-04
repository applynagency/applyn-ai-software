from pydantic import BaseModel, model_validator
from datetime import datetime
from typing import Optional
import re


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None

    @model_validator(mode="after")
    def set_slug(self) -> "WorkspaceCreate":
        if not self.slug:
            self.slug = re.sub(r"[^a-z0-9-]+", "-", self.name.lower()).strip("-")
        else:
            self.slug = re.sub(r"[^a-z0-9-]+", "-", self.slug.lower()).strip("-")
        return self


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    slug: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int
