from datetime import datetime

from pydantic import BaseModel

from app.models.requirement import RequirementStatus


class RequirementCreate(BaseModel):
    title: str
    content: str
    project_id: str


class RequirementUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    status: RequirementStatus | None = None


class RequirementResponse(BaseModel):
    id: str
    title: str
    content: str
    status: RequirementStatus
    project_id: str
    submitted_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequirementListResponse(BaseModel):
    items: list[RequirementResponse]
    total: int
