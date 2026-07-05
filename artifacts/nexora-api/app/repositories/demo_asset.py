"""Sprint 51C - data access for demo assets. All queries org-scoped."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.demo_asset import DemoAsset
from app.repositories.base import BaseRepository


class DemoAssetRepository(BaseRepository[DemoAsset]):
    def __init__(self, session: AsyncSession):
        super().__init__(DemoAsset, session)

    async def get_for_org(self, asset_id: str, organization_id: str) -> DemoAsset | None:
        stmt = select(DemoAsset).where(
            DemoAsset.id == asset_id,
            DemoAsset.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self,
        organization_id: str,
        *,
        category: str | None = None,
        asset_type: str | None = None,
        module: str | None = None,
        tag: str | None = None,
        search: str | None = None,
    ) -> list[DemoAsset]:
        conditions = [DemoAsset.organization_id == organization_id]
        if category:
            conditions.append(DemoAsset.category == category)
        if asset_type:
            conditions.append(DemoAsset.asset_type == asset_type)
        if module:
            conditions.append(DemoAsset.module == module)
        if search:
            like = f"%{search.strip()}%"
            conditions.append(
                or_(
                    DemoAsset.title.ilike(like),
                    DemoAsset.description.ilike(like),
                    DemoAsset.module.ilike(like),
                )
            )
        stmt = (
            select(DemoAsset)
            .where(*conditions)
            .order_by(
                DemoAsset.category.asc(),
                DemoAsset.order_index.asc(),
                DemoAsset.created_at.desc(),
            )
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        if tag:
            tag_l = tag.strip().lower()
            rows = [r for r in rows if any(tag_l == str(t).lower() for t in (r.tags or []))]
        return rows
