"""Sprint 45A — data access for intelligent runbooks (incl. search)."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runbook import Runbook
from app.repositories.base import BaseRepository


class RunbookRepository(BaseRepository[Runbook]):
    def __init__(self, session: AsyncSession):
        super().__init__(Runbook, session)

    async def get_for_org(self, runbook_id: str, organization_id: str) -> Runbook | None:
        stmt = select(Runbook).where(
            Runbook.id == runbook_id, Runbook.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_canonical(
        self, organization_id: str, category: str, service: str | None
    ) -> Runbook | None:
        """The latest generated runbook for a (category, service) pair."""
        stmt = select(Runbook).where(
            Runbook.organization_id == organization_id,
            Runbook.category == category,
            (Runbook.service == service) if service is not None else Runbook.service.is_(None),
        ).order_by(Runbook.created_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def search(
        self,
        organization_id: str,
        *,
        search: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Runbook], int]:
        filters = [Runbook.organization_id == organization_id]
        if category:
            filters.append(Runbook.category == category)
        if search:
            term = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(Runbook.title).like(term),
                    func.lower(Runbook.category).like(term),
                    func.coalesce(func.lower(Runbook.service), "").like(term),
                    func.coalesce(Runbook.search_text, "").like(term),
                )
            )
        count_stmt = select(func.count()).select_from(Runbook).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = (
            select(Runbook)
            .where(*filters)
            .order_by(Runbook.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows, total
