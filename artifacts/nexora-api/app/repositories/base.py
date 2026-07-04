from typing import Any, Generic, TypeVar

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base, utcnow

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: str, include_deleted: bool = False) -> ModelType | None:
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        filters: list[Any] | None = None,
        offset: int = 0,
        limit: int = 50,
        include_deleted: bool = False,
        options: list[Any] | None = None,
    ) -> tuple[list[ModelType], int]:
        conditions = []
        if not include_deleted and hasattr(self.model, "deleted_at"):
            conditions.append(self.model.deleted_at.is_(None))
        if filters:
            conditions.extend(filters)

        where_clause = and_(*conditions) if conditions else None

        count_stmt = select(func.count()).select_from(self.model)
        data_stmt = select(self.model)

        if where_clause is not None:
            count_stmt = count_stmt.where(where_clause)
            data_stmt = data_stmt.where(where_clause)

        # Eager-load relationships in the same query batch to avoid N+1 fetches
        # when callers need related rows for every item in the page.
        if options:
            data_stmt = data_stmt.options(*options)

        data_stmt = data_stmt.offset(offset).limit(limit)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        data_result = await self.session.execute(data_stmt)
        items = list(data_result.scalars().all())

        return items, total

    async def create(self, **kwargs: Any) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.updated_at = utcnow()
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, instance: ModelType) -> ModelType:
        if hasattr(instance, "soft_delete"):
            instance.soft_delete()
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def hard_delete(self, instance: ModelType) -> None:
        await self.session.delete(instance)
        await self.session.flush()
