"""Data access for collaborative war-room entities.

Participants (human presence/membership), attachments (uploaded files),
evidence (pinned items), and war-room-scoped approvals. All queries are
org-scoped.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import utcnow
from app.models.war_room import (
    WarRoomApproval,
    WarRoomAttachment,
    WarRoomEvidence,
    WarRoomParticipant,
)
from app.repositories.base import BaseRepository


class WarRoomParticipantRepository(BaseRepository[WarRoomParticipant]):
    def __init__(self, session: AsyncSession):
        super().__init__(WarRoomParticipant, session)

    async def get(self, war_room_id: str, user_id: str) -> WarRoomParticipant | None:
        stmt = select(WarRoomParticipant).where(
            WarRoomParticipant.war_room_id == war_room_id,
            WarRoomParticipant.user_id == user_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_room(
        self, war_room_id: str, organization_id: str, *, active_only: bool = False
    ) -> list[WarRoomParticipant]:
        stmt = select(WarRoomParticipant).where(
            WarRoomParticipant.war_room_id == war_room_id,
            WarRoomParticipant.organization_id == organization_id,
        )
        if active_only:
            stmt = stmt.where(WarRoomParticipant.is_active.is_(True))
        stmt = stmt.order_by(WarRoomParticipant.created_at.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def upsert(
        self,
        *,
        war_room_id: str,
        organization_id: str,
        user_id: str,
        user_name: str | None,
        role: str | None,
        is_active: bool = True,
    ) -> WarRoomParticipant:
        existing = await self.get(war_room_id, user_id)
        if existing is not None:
            existing.is_active = is_active
            existing.last_seen_at = utcnow()
            if user_name:
                existing.user_name = user_name
            if role:
                existing.role = role
            await self.session.flush()
            return existing
        return await self.create(
            war_room_id=war_room_id,
            organization_id=organization_id,
            user_id=user_id,
            user_name=user_name,
            role=role,
            is_active=is_active,
            last_seen_at=utcnow(),
        )


class WarRoomAttachmentRepository(BaseRepository[WarRoomAttachment]):
    def __init__(self, session: AsyncSession):
        super().__init__(WarRoomAttachment, session)

    async def get_for_room(
        self, attachment_id: str, war_room_id: str, organization_id: str
    ) -> WarRoomAttachment | None:
        stmt = select(WarRoomAttachment).where(
            WarRoomAttachment.id == attachment_id,
            WarRoomAttachment.war_room_id == war_room_id,
            WarRoomAttachment.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_room(
        self, war_room_id: str, organization_id: str
    ) -> list[WarRoomAttachment]:
        stmt = (
            select(WarRoomAttachment)
            .where(
                WarRoomAttachment.war_room_id == war_room_id,
                WarRoomAttachment.organization_id == organization_id,
            )
            .order_by(WarRoomAttachment.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class WarRoomEvidenceRepository(BaseRepository[WarRoomEvidence]):
    def __init__(self, session: AsyncSession):
        super().__init__(WarRoomEvidence, session)

    async def list_for_room(
        self, war_room_id: str, organization_id: str
    ) -> list[WarRoomEvidence]:
        stmt = (
            select(WarRoomEvidence)
            .where(
                WarRoomEvidence.war_room_id == war_room_id,
                WarRoomEvidence.organization_id == organization_id,
            )
            .order_by(WarRoomEvidence.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class WarRoomApprovalRepository(BaseRepository[WarRoomApproval]):
    def __init__(self, session: AsyncSession):
        super().__init__(WarRoomApproval, session)

    async def get_for_room(
        self, approval_id: str, war_room_id: str, organization_id: str
    ) -> WarRoomApproval | None:
        stmt = select(WarRoomApproval).where(
            WarRoomApproval.id == approval_id,
            WarRoomApproval.war_room_id == war_room_id,
            WarRoomApproval.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_room(
        self, war_room_id: str, organization_id: str
    ) -> list[WarRoomApproval]:
        stmt = (
            select(WarRoomApproval)
            .where(
                WarRoomApproval.war_room_id == war_room_id,
                WarRoomApproval.organization_id == organization_id,
            )
            .order_by(WarRoomApproval.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
