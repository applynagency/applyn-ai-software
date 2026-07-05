"""Repository for integration onboarding sessions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration_onboarding import IntegrationOnboardingSession


class IntegrationOnboardingRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_org(self, session_id: str, organization_id: str) -> IntegrationOnboardingSession | None:
        stmt = select(IntegrationOnboardingSession).where(
            IntegrationOnboardingSession.id == session_id,
            IntegrationOnboardingSession.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, status: str | None = None,
    ) -> list[IntegrationOnboardingSession]:
        stmt = select(IntegrationOnboardingSession).where(
            IntegrationOnboardingSession.organization_id == organization_id,
        ).order_by(IntegrationOnboardingSession.created_at.desc())
        if status:
            stmt = stmt.where(IntegrationOnboardingSession.status == status)
        return list((await self.session.execute(stmt)).scalars().all())
