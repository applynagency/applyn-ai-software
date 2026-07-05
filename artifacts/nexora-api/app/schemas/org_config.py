from datetime import datetime

from pydantic import BaseModel, Field


class OrgVariableCreate(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: str
    environment: str = Field(default="default", max_length=40)
    description: str | None = None
    is_secret: bool = False


class OrgVariableUpdate(BaseModel):
    value: str | None = None
    description: str | None = None
    is_secret: bool | None = None


class OrgVariableView(BaseModel):
    id: str
    key: str
    environment: str
    description: str | None = None
    is_secret: bool
    has_value: bool = True
    value_preview: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
