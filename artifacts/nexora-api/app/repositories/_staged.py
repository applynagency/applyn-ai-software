"""Shared CRUD for staged agent run/artifact repositories.

Every staged code-generation family (Backend/Frontend V1/V2/V3, and the various
architect/execution/review repos that follow the same shape) historically
duplicated the identical ``get_with_artifact`` / ``list_by_requirement`` /
``list_by_organization`` (run repo) and ``get_for_org`` / ``get_run_for_org``
(artifact repo) queries, differing only in the ORM model names.

``StagedRunRepository`` and ``StagedArtifactRepository`` provide those queries
once on top of :class:`app.repositories.base.BaseRepository`. They assume the
conventional schema used across the project:

* the run model exposes an ``artifacts`` relationship and ``id``,
  ``requirement_id``, ``organization_id`` and ``created_at`` columns;
* the artifact model exposes ``id`` and a ``run_id`` foreign key to the run.
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository, ModelType


class StagedRunRepository(BaseRepository[ModelType]):
    """Run repository with artifact eager-loading and standard listings."""

    async def get_with_artifact(self, run_id: str) -> ModelType | None:
        stmt = (
            select(self.model)
            .where(self.model.id == run_id)
            .options(selectinload(self.model.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ModelType], int]:
        stmt = (
            select(self.model)
            .where(self.model.requirement_id == requirement_id)
            .options(selectinload(self.model.artifacts))
            .order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(self.model).where(self.model.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ModelType], int]:
        stmt = (
            select(self.model)
            .where(self.model.organization_id == organization_id)
            .options(selectinload(self.model.artifacts))
            .order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(self.model).where(self.model.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class StagedArtifactRepository(BaseRepository[ModelType]):
    """Artifact repository with org-scoped lookups joined through the run.

    Subclasses must set the ``run_model`` class attribute to the owning run
    model so the org-scoping join can be expressed generically.
    """

    run_model: type

    async def get_for_org(self, artifact_id: str, organization_id: str) -> ModelType | None:
        stmt = (
            select(self.model)
            .join(self.run_model, self.model.run_id == self.run_model.id)
            .where(
                self.model.id == artifact_id,
                self.run_model.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_run_for_org(self, run_id: str, organization_id: str):
        stmt = select(self.run_model).where(
            self.run_model.id == run_id,
            self.run_model.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
