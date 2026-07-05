"""Discovery scan-run progress schema (shared by Universal Discovery)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ScanProgressView(BaseModel):
    id: str
    organization_id: str
    status: str
    trigger: str
    providers: list[str] = Field(default_factory=list)
    connection_count: int = 0
    scanned_connections: int = 0
    current_provider: str | None = None
    current_account: str | None = None
    resources_found: int = 0
    estimated_seconds: int | None = None
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("providers", "warnings", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return v or []
