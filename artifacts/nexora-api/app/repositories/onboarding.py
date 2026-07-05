"""Sprint 47C - data access for the Guided Setup Wizard."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding import OnboardingSession, OnboardingStatus
from app.repositories.base import BaseRepository


class OnboardingSessionRepository(BaseRepository[OnboardingSession]):
    def __init__(self, session: AsyncSession):
        super().__init__(OnboardingSession, session)

    async def get_for_org(self, session_id: str, organization_id: str) -> OnboardingSession | None:
        stmt = select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_in_progress(self, organization_id: str) -> OnboardingSession | None:
        stmt = (
            select(OnboardingSession)
            .where(
                OnboardingSession.organization_id == organization_id,
                OnboardingSession.status == OnboardingStatus.IN_PROGRESS.value,
            )
            .order_by(OnboardingSession.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
