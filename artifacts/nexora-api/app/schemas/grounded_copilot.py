"""Schemas for the grounded copilot API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CopilotFilters(BaseModel):
    service: str | None = None
    environment: str | None = None
    provider: str | None = None
    incident_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class Citation(BaseModel):
    source: str
    id: str | None = None
    label: str
    detail: str | None = None


class RetrievedSource(BaseModel):
    source: str
    id: str | None = None
    label: str
    score: float | None = None


class ToolCall(BaseModel):
    tool: str
    input: dict[str, Any] = {}
    ok: bool = False


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    filters: CopilotFilters | None = None


class CopilotChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    intent: str
    citations: list[Citation] = []
    sources: list[RetrievedSource] = []
    tool_calls: list[ToolCall] = []
    confidence: int = 0
    grounded: bool = False
    generation_mode: str = "offline"
    model: str = "offline"
    low_confidence: bool = False
    retrieval_provider: str = "offline-hash"
    suggested_questions: list[str] = []


class CopilotMessageView(BaseModel):
    id: str
    role: str
    content: str
    intent: str | None = None
    citations: list[Citation] | None = None
    sources: list[RetrievedSource] | None = None
    tool_calls: list[ToolCall] | None = None
    confidence: int | None = None
    grounded: bool | None = None
    generation_mode: str | None = None
    model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CopilotConversationView(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class CopilotConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[CopilotMessageView]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
