from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
import re


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None

    @field_validator("slug", mode="before")
    @classmethod
    def generate_slug(cls, v: Optional[str], info) -> str:
        if v:
            return re.sub(r"[^a-z0-9-]", "-", v.lower())
        name = info.data.get("name", "workspace")
        return re.sub(r"[^a-z0-9-]", "-", name.lower())


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
