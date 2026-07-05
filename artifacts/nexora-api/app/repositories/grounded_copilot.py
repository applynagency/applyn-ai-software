"""Repositories for grounded copilot conversations and messages."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grounded_copilot import (
    GroundedCopilotConversation,
    GroundedCopilotMessage,
)
from app.repositories.base import BaseRepository


class GroundedCopilotConversationRepository(BaseRepository[GroundedCopilotConversation]):
    def __init__(self, session: AsyncSession):
        super().__init__(GroundedCopilotConversation, session)

    async def get_for_org(
        self, conversation_id: str, organization_id: str
    ) -> GroundedCopilotConversation | None:
        result = await self.session.execute(
            select(GroundedCopilotConversation).where(
                GroundedCopilotConversation.id == conversation_id,
                GroundedCopilotConversation.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, limit: int = 50
    ) -> list[GroundedCopilotConversation]:
        result = await self.session.execute(
            select(GroundedCopilotConversation)
            .where(GroundedCopilotConversation.organization_id == organization_id)
            .order_by(GroundedCopilotConversation.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class GroundedCopilotMessageRepository(BaseRepository[GroundedCopilotMessage]):
    def __init__(self, session: AsyncSession):
        super().__init__(GroundedCopilotMessage, session)

    async def list_for_conversation(
        self, conversation_id: str, organization_id: str, *, limit: int | None = None
    ) -> list[GroundedCopilotMessage]:
        stmt = (
            select(GroundedCopilotMessage)
            .where(
                GroundedCopilotMessage.conversation_id == conversation_id,
                GroundedCopilotMessage.organization_id == organization_id,
            )
            .order_by(GroundedCopilotMessage.created_at.asc(), GroundedCopilotMessage.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_conversation(self, conversation_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(GroundedCopilotMessage)
            .where(GroundedCopilotMessage.conversation_id == conversation_id)
        )
        return int(result.scalar_one())
