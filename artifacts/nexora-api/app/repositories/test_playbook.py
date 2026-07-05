"""Sprint 51B - data access for the Test Playbook Engine. All queries org-scoped."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_playbook import TestPlaybook, TestPlaybookRun, TestPlaybookStep
from app.repositories.base import BaseRepository


class TestPlaybookRepository(BaseRepository[TestPlaybook]):
    def __init__(self, session: AsyncSession):
        super().__init__(TestPlaybook, session)

    async def get_for_org(self, playbook_id: str, organization_id: str) -> TestPlaybook | None:
        stmt = select(TestPlaybook).where(
            TestPlaybook.id == playbook_id,
            TestPlaybook.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, category: str | None = None, search: str | None = None
    ) -> list[TestPlaybook]:
        conditions = [TestPlaybook.organization_id == organization_id]
        if category:
            conditions.append(TestPlaybook.category == category)
        if search:
            like = f"%{search.strip()}%"
            conditions.append(TestPlaybook.name.ilike(like))
        stmt = (
            select(TestPlaybook)
            .where(*conditions)
            .order_by(TestPlaybook.category.asc(), TestPlaybook.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class TestPlaybookStepRepository(BaseRepository[TestPlaybookStep]):
    def __init__(self, session: AsyncSession):
        super().__init__(TestPlaybookStep, session)

    async def list_for_playbook(self, playbook_id: str, organization_id: str) -> list[TestPlaybookStep]:
        stmt = (
            select(TestPlaybookStep)
            .where(
                TestPlaybookStep.playbook_id == playbook_id,
                TestPlaybookStep.organization_id == organization_id,
            )
            .order_by(TestPlaybookStep.order_index.asc(), TestPlaybookStep.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete_for_playbook(self, playbook_id: str, organization_id: str) -> None:
        for step in await self.list_for_playbook(playbook_id, organization_id):
            await self.session.delete(step)
        await self.session.flush()


class TestPlaybookRunRepository(BaseRepository[TestPlaybookRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(TestPlaybookRun, session)

    async def get_for_org(self, run_id: str, organization_id: str) -> TestPlaybookRun | None:
        stmt = select(TestPlaybookRun).where(
            TestPlaybookRun.id == run_id,
            TestPlaybookRun.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_playbook(self, playbook_id: str, organization_id: str) -> list[TestPlaybookRun]:
        stmt = (
            select(TestPlaybookRun)
            .where(
                TestPlaybookRun.playbook_id == playbook_id,
                TestPlaybookRun.organization_id == organization_id,
            )
            .order_by(TestPlaybookRun.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_for_playbook(self, playbook_id: str) -> int:
        stmt = select(func.count()).select_from(
            select(TestPlaybookRun).where(TestPlaybookRun.playbook_id == playbook_id).subquery()
        )
        return int((await self.session.execute(stmt)).scalar_one())
