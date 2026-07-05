"""Sprint 51D - data access for product tours. All queries org-scoped."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_tour import ProductTour, ProductTourProgress, ProductTourStep
from app.repositories.base import BaseRepository


class ProductTourRepository(BaseRepository[ProductTour]):
    def __init__(self, session: AsyncSession):
        super().__init__(ProductTour, session)

    async def get_for_org(self, tour_id: str, organization_id: str) -> ProductTour | None:
        stmt = select(ProductTour).where(
            ProductTour.id == tour_id,
            ProductTour.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_key(self, key: str, organization_id: str) -> ProductTour | None:
        stmt = select(ProductTour).where(
            ProductTour.key == key,
            ProductTour.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_for_org(
        self, organization_id: str, *, audience: str | None = None, first_login: bool | None = None
    ) -> list[ProductTour]:
        conditions = [ProductTour.organization_id == organization_id]
        if audience:
            conditions.append(ProductTour.audience == audience)
        if first_login is not None:
            conditions.append(ProductTour.is_first_login.is_(first_login))
        stmt = (
            select(ProductTour)
            .where(*conditions)
            .order_by(ProductTour.order_index.asc(), ProductTour.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ProductTourStepRepository(BaseRepository[ProductTourStep]):
    def __init__(self, session: AsyncSession):
        super().__init__(ProductTourStep, session)

    async def list_for_tour(self, tour_id: str, organization_id: str) -> list[ProductTourStep]:
        stmt = (
            select(ProductTourStep)
            .where(
                ProductTourStep.tour_id == tour_id,
                ProductTourStep.organization_id == organization_id,
            )
            .order_by(ProductTourStep.order_index.asc(), ProductTourStep.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_module(self, module: str, organization_id: str) -> list[ProductTourStep]:
        stmt = (
            select(ProductTourStep)
            .where(
                ProductTourStep.module == module,
                ProductTourStep.organization_id == organization_id,
            )
            .order_by(ProductTourStep.order_index.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ProductTourProgressRepository(BaseRepository[ProductTourProgress]):
    def __init__(self, session: AsyncSession):
        super().__init__(ProductTourProgress, session)

    async def get_for_user(
        self, tour_id: str, user_id: str, organization_id: str
    ) -> ProductTourProgress | None:
        stmt = select(ProductTourProgress).where(
            ProductTourProgress.tour_id == tour_id,
            ProductTourProgress.user_id == user_id,
            ProductTourProgress.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_for_user(self, user_id: str, organization_id: str) -> list[ProductTourProgress]:
        stmt = select(ProductTourProgress).where(
            ProductTourProgress.user_id == user_id,
            ProductTourProgress.organization_id == organization_id,
        )
        return list((await self.session.execute(stmt)).scalars().all())
