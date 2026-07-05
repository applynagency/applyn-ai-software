"""Sprint 46C - data access for Executive Reliability Reports."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.executive_report import ExecutiveReport
from app.repositories.base import BaseRepository


class ExecutiveReportRepository(BaseRepository[ExecutiveReport]):
    def __init__(self, session: AsyncSession):
        super().__init__(ExecutiveReport, session)

    async def get_for_org(self, report_id: str, organization_id: str) -> ExecutiveReport | None:
        stmt = select(ExecutiveReport).where(
            ExecutiveReport.id == report_id,
            ExecutiveReport.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, report_type: str | None = None, limit: int = 100
    ) -> list[ExecutiveReport]:
        stmt = select(ExecutiveReport).where(ExecutiveReport.organization_id == organization_id)
        if report_type:
            stmt = stmt.where(ExecutiveReport.report_type == report_type)
        stmt = stmt.order_by(ExecutiveReport.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest_of_type(
        self, organization_id: str, report_type: str
    ) -> ExecutiveReport | None:
        stmt = (
            select(ExecutiveReport)
            .where(
                ExecutiveReport.organization_id == organization_id,
                ExecutiveReport.report_type == report_type,
            )
            .order_by(ExecutiveReport.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
