"""Sprint 51A - data access for the Product Documentation Center.

All queries are org-scoped to enforce tenant isolation.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documentation import DocumentationArticle, DocumentationCategory
from app.repositories.base import BaseRepository


class DocumentationCategoryRepository(BaseRepository[DocumentationCategory]):
    def __init__(self, session: AsyncSession):
        super().__init__(DocumentationCategory, session)

    async def list_for_org(self, organization_id: str) -> list[DocumentationCategory]:
        stmt = (
            select(DocumentationCategory)
            .where(DocumentationCategory.organization_id == organization_id)
            .order_by(DocumentationCategory.order_index.asc(), DocumentationCategory.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_org(self, category_id: str, organization_id: str) -> DocumentationCategory | None:
        stmt = select(DocumentationCategory).where(
            DocumentationCategory.id == category_id,
            DocumentationCategory.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_key(self, key: str, organization_id: str) -> DocumentationCategory | None:
        stmt = select(DocumentationCategory).where(
            DocumentationCategory.key == key,
            DocumentationCategory.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def count_for_org(self, organization_id: str) -> int:
        stmt = select(func.count()).select_from(
            select(DocumentationCategory)
            .where(DocumentationCategory.organization_id == organization_id)
            .subquery()
        )
        return int((await self.session.execute(stmt)).scalar_one())


class DocumentationArticleRepository(BaseRepository[DocumentationArticle]):
    def __init__(self, session: AsyncSession):
        super().__init__(DocumentationArticle, session)

    async def get_for_org(self, article_id: str, organization_id: str) -> DocumentationArticle | None:
        stmt = select(DocumentationArticle).where(
            DocumentationArticle.id == article_id,
            DocumentationArticle.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str, organization_id: str) -> DocumentationArticle | None:
        stmt = select(DocumentationArticle).where(
            DocumentationArticle.slug == slug,
            DocumentationArticle.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def slug_exists(self, slug: str, organization_id: str, exclude_id: str | None = None) -> bool:
        stmt = select(DocumentationArticle.id).where(
            DocumentationArticle.slug == slug,
            DocumentationArticle.organization_id == organization_id,
        )
        if exclude_id:
            stmt = stmt.where(DocumentationArticle.id != exclude_id)
        return (await self.session.execute(stmt)).first() is not None

    async def list_for_org(
        self,
        organization_id: str,
        *,
        category_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DocumentationArticle], int]:
        conditions = [DocumentationArticle.organization_id == organization_id]
        if category_id:
            conditions.append(DocumentationArticle.category_id == category_id)
        if status:
            conditions.append(DocumentationArticle.status == status)
        if search:
            like = f"%{search.strip()}%"
            conditions.append(
                or_(
                    DocumentationArticle.title.ilike(like),
                    DocumentationArticle.summary.ilike(like),
                    DocumentationArticle.content.ilike(like),
                    DocumentationArticle.slug.ilike(like),
                )
            )

        count_stmt = select(func.count()).select_from(
            select(DocumentationArticle).where(*conditions).subquery()
        )
        total = int((await self.session.execute(count_stmt)).scalar_one())

        data_stmt = (
            select(DocumentationArticle)
            .where(*conditions)
            .order_by(
                DocumentationArticle.order_index.asc(),
                DocumentationArticle.title.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.session.execute(data_stmt)).scalars().all())
        return items, total

    async def list_by_category(self, organization_id: str) -> list[DocumentationArticle]:
        """All articles for an org, ordered, for navigation-tree assembly."""
        stmt = (
            select(DocumentationArticle)
            .where(DocumentationArticle.organization_id == organization_id)
            .order_by(
                DocumentationArticle.order_index.asc(),
                DocumentationArticle.title.asc(),
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())
