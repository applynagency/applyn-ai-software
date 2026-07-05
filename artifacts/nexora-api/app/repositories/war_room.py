"""Sprint 46D - data access for AI Incident War Rooms."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.war_room import WarRoom, WarRoomMessage
from app.repositories.base import BaseRepository


class WarRoomRepository(BaseRepository[WarRoom]):
    def __init__(self, session: AsyncSession):
        super().__init__(WarRoom, session)

    async def get_for_org(self, war_room_id: str, organization_id: str) -> WarRoom | None:
        stmt = select(WarRoom).where(
            WarRoom.id == war_room_id,
            WarRoom.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str, *, limit: int = 100) -> list[WarRoom]:
        stmt = (
            select(WarRoom)
            .where(WarRoom.organization_id == organization_id)
            .order_by(WarRoom.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_incident(self, incident_id: str, organization_id: str) -> WarRoom | None:
        stmt = (
            select(WarRoom)
            .where(
                WarRoom.incident_id == incident_id,
                WarRoom.organization_id == organization_id,
            )
            .order_by(WarRoom.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class WarRoomMessageRepository(BaseRepository[WarRoomMessage]):
    def __init__(self, session: AsyncSession):
        super().__init__(WarRoomMessage, session)

    async def list_for_room(self, war_room_id: str, organization_id: str) -> list[WarRoomMessage]:
        stmt = (
            select(WarRoomMessage)
            .where(
                WarRoomMessage.war_room_id == war_room_id,
                WarRoomMessage.organization_id == organization_id,
            )
            .order_by(WarRoomMessage.sequence.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_for_room(self, war_room_id: str, organization_id: str) -> int:
        stmt = select(func.count()).select_from(WarRoomMessage).where(
            WarRoomMessage.war_room_id == war_room_id,
            WarRoomMessage.organization_id == organization_id,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def get_for_room(
        self, message_id: str, war_room_id: str, organization_id: str
    ) -> WarRoomMessage | None:
        stmt = select(WarRoomMessage).where(
            WarRoomMessage.id == message_id,
            WarRoomMessage.war_room_id == war_room_id,
            WarRoomMessage.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_thread(
        self, parent_message_id: str, organization_id: str
    ) -> list[WarRoomMessage]:
        """Replies to a message, oldest first (the thread under a root message)."""
        stmt = (
            select(WarRoomMessage)
            .where(
                WarRoomMessage.parent_message_id == parent_message_id,
                WarRoomMessage.organization_id == organization_id,
            )
            .order_by(WarRoomMessage.sequence.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def next_sequence(self, war_room_id: str, organization_id: str) -> int:
        stmt = select(func.max(WarRoomMessage.sequence)).where(
            WarRoomMessage.war_room_id == war_room_id,
            WarRoomMessage.organization_id == organization_id,
        )
        current = (await self.session.execute(stmt)).scalar_one_or_none()
        return (current + 1) if current is not None else 0
