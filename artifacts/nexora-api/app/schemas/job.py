"""Schemas for the async job status API."""

from __future__ import annotations

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    organization_id: str | None = None
    created_by: str | None = None
    arq_job_id: str | None = None
    progress: int = 0
    progress_message: str | None = None
    attempts: int = 0
    max_attempts: int = 0
    cancel_requested: bool = False
    params: dict | None = None
    result: dict | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    offset: int
    limit: int
