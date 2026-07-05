"""Copilot API — the single, unified AI assistant (``/v1/copilot``).

* POST /v1/copilot/chat               - grounded LLM answer (RAG + graph + tools)
* POST /v1/copilot/chat/stream        - same, streamed as Server-Sent Events
* GET  /v1/copilot/conversations      - list conversations
* GET  /v1/copilot/conversations/{id} - conversation + message history
* GET  /v1/copilot/suggested-questions

The one Copilot surface. Internally it composes an LLM, retrieval (RAG), the
knowledge graph, and a deterministic evidence provider
(``app.services.grounded_copilot.evidence``) as grounded tools. Read-only over
org-scoped data; audited; answers are grounded in retrieved records with
citations, confidence scoring, and hallucination prevention; never returns
secrets or mutates.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.config import settings
from app.schemas.grounded_copilot import (
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotConversationDetail,
    CopilotConversationView,
    CopilotMessageView,
)
from app.services.grounded_copilot.engine import SUGGESTED_QUESTIONS, GroundedCopilotEngine

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.post("/chat", response_model=CopilotChatResponse)
async def chat(
    data: CopilotChatRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    result = await GroundedCopilotEngine(session).chat(current_user, org_context, data)
    return CopilotChatResponse(**result)


@router.post("/chat/stream")
async def chat_stream(
    data: CopilotChatRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    if not settings.COPILOT_STREAMING_ENABLED:
        raise HTTPException(status_code=503, detail="Copilot streaming is disabled.")

    engine = GroundedCopilotEngine(session)

    async def event_stream():
        async for event in engine.stream_chat(current_user, org_context, data):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[CopilotConversationView])
async def list_conversations(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    rows = await GroundedCopilotEngine(session).list_conversations(current_user, org_context)
    return [
        CopilotConversationView(
            id=c.id,
            title=c.title,
            message_count=count,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c, count in rows
    ]


@router.get("/conversations/{conversation_id}", response_model=CopilotConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    conv, messages = await GroundedCopilotEngine(session).get_conversation(
        current_user, org_context, conversation_id
    )
    return CopilotConversationDetail(
        id=conv.id,
        title=conv.title,
        messages=[CopilotMessageView.model_validate(m) for m in messages],
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/suggested-questions", response_model=list[str])
async def suggested_questions(
    current_user: CurrentUser,
    org_context: OrgContextDep,
):
    return SUGGESTED_QUESTIONS
