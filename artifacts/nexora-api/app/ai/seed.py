"""Default global prompt seeding (Sprint 61D).

Registers a baseline set of global prompts (``organization_id is None``) that any
organization can override. Idempotent — only registers a key when it is absent.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import PromptRegistry
from app.models.ai_platform import PromptTemplate

DEFAULT_PROMPTS: list[dict] = [
    {
        "key": "copilot.system",
        "template": (
            "You are Nexora's grounded reliability copilot. Answer using only the "
            "provided context and cite sources. Question: {question}\nContext: {context}"
        ),
        "description": "Grounded copilot system/answer prompt.",
    },
    {
        "key": "summarize",
        "template": "Summarize the following concisely:\n{text}",
        "description": "Generic summarization prompt.",
    },
    {
        "key": "incident.analysis",
        "template": (
            "Analyze this incident and propose next actions.\n"
            "Title: {title}\nSignals: {signals}\nGraph context: {graph}"
        ),
        "description": "Incident analysis prompt.",
    },
]


async def seed_default_prompts(session: AsyncSession) -> int:
    registry = PromptRegistry(session)
    created = 0
    for spec in DEFAULT_PROMPTS:
        exists = await session.scalar(
            select(PromptTemplate.id).where(
                PromptTemplate.key == spec["key"],
                PromptTemplate.organization_id.is_(None),
            )
        )
        if exists:
            continue
        await registry.register(
            key=spec["key"], template=spec["template"], organization_id=None,
            description=spec.get("description"))
        created += 1
    return created
