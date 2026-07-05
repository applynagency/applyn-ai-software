"""Repositories for the delivery platform."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery import (
    DeliveryArtifact,
    DeliveryDeployment,
    DeliveryEnvironment,
    DeliveryGitOpsApp,
    DeliveryOperation,
    DeliveryPipeline,
    DeliveryPipelineRun,
    DeliveryRelease,
    DeliveryRepository,
    DeliverySecurityScan,
    SourceConnection,
)
from app.repositories.base import BaseRepository


class SourceConnectionRepository(BaseRepository[SourceConnection]):
    def __init__(self, session: AsyncSession):
        super().__init__(SourceConnection, session)

    async def list_for_org(self, organization_id: str) -> list[SourceConnection]:
        items, _ = await self.list_all(
            filters=[SourceConnection.organization_id == organization_id, SourceConnection.is_active.is_(True)],
            limit=100,
        )
        return items


class DeliveryRepositoryRepository(BaseRepository[DeliveryRepository]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryRepository, session)

    async def replace_for_connection(
        self, organization_id: str, connection_id: str, rows: list[dict],
    ) -> int:
        await self.session.execute(
            delete(DeliveryRepository).where(
                DeliveryRepository.organization_id == organization_id,
                DeliveryRepository.connection_id == connection_id,
            )
        )
        for row in rows:
            await self.create(organization_id=organization_id, connection_id=connection_id, **row)
        return len(rows)

    async def list_for_org(self, organization_id: str) -> list[DeliveryRepository]:
        items, _ = await self.list_all(
            filters=[DeliveryRepository.organization_id == organization_id], limit=500,
        )
        return items

    async def get_for_org(self, repo_id: str, organization_id: str) -> DeliveryRepository | None:
        stmt = select(DeliveryRepository).where(
            DeliveryRepository.id == repo_id,
            DeliveryRepository.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class DeliveryPipelineRepository(BaseRepository[DeliveryPipeline]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryPipeline, session)

    async def replace_for_repo(
        self, organization_id: str, repository_id: str, rows: list[dict],
    ) -> int:
        await self.session.execute(
            delete(DeliveryPipeline).where(
                DeliveryPipeline.organization_id == organization_id,
                DeliveryPipeline.repository_id == repository_id,
            )
        )
        for row in rows:
            await self.create(organization_id=organization_id, repository_id=repository_id, **row)
        return len(rows)

    async def replace_for_integration(
        self, organization_id: str, integration_connection_id: str, rows: list[dict],
    ) -> int:
        await self.session.execute(
            delete(DeliveryPipeline).where(
                DeliveryPipeline.organization_id == organization_id,
                DeliveryPipeline.integration_connection_id == integration_connection_id,
            )
        )
        for row in rows:
            await self.create(
                organization_id=organization_id,
                integration_connection_id=integration_connection_id,
                repository_id=None,
                **row,
            )
        return len(rows)

    async def list_for_org(self, organization_id: str) -> list[DeliveryPipeline]:
        items, _ = await self.list_all(
            filters=[DeliveryPipeline.organization_id == organization_id], limit=500,
        )
        return items


class DeliveryPipelineRunRepository(BaseRepository[DeliveryPipelineRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryPipelineRun, session)

    async def replace_for_pipeline(
        self, organization_id: str, pipeline_id: str, rows: list[dict],
    ) -> int:
        await self.session.execute(
            delete(DeliveryPipelineRun).where(
                DeliveryPipelineRun.organization_id == organization_id,
                DeliveryPipelineRun.pipeline_id == pipeline_id,
            )
        )
        for row in rows:
            await self.create(organization_id=organization_id, pipeline_id=pipeline_id, **row)
        return len(rows)

    async def list_for_org(self, organization_id: str, *, limit: int = 100) -> list[DeliveryPipelineRun]:
        stmt = (
            select(DeliveryPipelineRun)
            .where(DeliveryPipelineRun.organization_id == organization_id)
            .order_by(DeliveryPipelineRun.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class DeliveryEnvironmentRepository(BaseRepository[DeliveryEnvironment]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryEnvironment, session)

    async def list_for_org(self, organization_id: str) -> list[DeliveryEnvironment]:
        stmt = (
            select(DeliveryEnvironment)
            .where(
                DeliveryEnvironment.organization_id == organization_id,
                DeliveryEnvironment.is_active.is_(True),
            )
            .order_by(DeliveryEnvironment.sort_order)
            .limit(20)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_org(self, env_id: str, organization_id: str) -> DeliveryEnvironment | None:
        stmt = select(DeliveryEnvironment).where(
            DeliveryEnvironment.id == env_id,
            DeliveryEnvironment.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class DeliveryArtifactRepository(BaseRepository[DeliveryArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryArtifact, session)

    async def list_for_org(self, organization_id: str) -> list[DeliveryArtifact]:
        items, _ = await self.list_all(
            filters=[DeliveryArtifact.organization_id == organization_id], limit=500,
        )
        return items


class DeliveryReleaseRepository(BaseRepository[DeliveryRelease]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryRelease, session)

    async def list_for_org(self, organization_id: str) -> list[DeliveryRelease]:
        stmt = (
            select(DeliveryRelease)
            .where(DeliveryRelease.organization_id == organization_id)
            .order_by(DeliveryRelease.created_at.desc())
            .limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class DeliveryDeploymentRepository(BaseRepository[DeliveryDeployment]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryDeployment, session)

    async def list_for_org(self, organization_id: str) -> list[DeliveryDeployment]:
        stmt = (
            select(DeliveryDeployment)
            .where(DeliveryDeployment.organization_id == organization_id)
            .order_by(DeliveryDeployment.created_at.desc())
            .limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_org(self, deployment_id: str, organization_id: str) -> DeliveryDeployment | None:
        stmt = select(DeliveryDeployment).where(
            DeliveryDeployment.id == deployment_id,
            DeliveryDeployment.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org_filtered(
        self,
        organization_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        environment_id: str | None = None,
        service: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[DeliveryDeployment], int]:
        filters = [DeliveryDeployment.organization_id == organization_id]
        if status:
            filters.append(DeliveryDeployment.status == status)
        if environment_id:
            filters.append(DeliveryDeployment.environment_id == environment_id)
        if service:
            filters.append(DeliveryDeployment.image_ref.ilike(f"%{service}%"))
        if date_from:
            filters.append(DeliveryDeployment.created_at >= date_from)
        if date_to:
            filters.append(DeliveryDeployment.created_at <= date_to)

        count_stmt = select(DeliveryDeployment).where(*filters)
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))

        stmt = (
            select(DeliveryDeployment)
            .where(*filters)
            .order_by(DeliveryDeployment.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total


class DeliverySecurityScanRepository(BaseRepository[DeliverySecurityScan]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliverySecurityScan, session)

    async def list_for_org(self, organization_id: str) -> list[DeliverySecurityScan]:
        items, _ = await self.list_all(
            filters=[DeliverySecurityScan.organization_id == organization_id], limit=100,
        )
        return items


class DeliveryGitOpsAppRepository(BaseRepository[DeliveryGitOpsApp]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryGitOpsApp, session)

    async def replace_for_org(self, organization_id: str, rows: list[dict]) -> int:
        await self.session.execute(
            delete(DeliveryGitOpsApp).where(DeliveryGitOpsApp.organization_id == organization_id)
        )
        for row in rows:
            await self.create(organization_id=organization_id, **row)
        return len(rows)

    async def list_for_org(self, organization_id: str) -> list[DeliveryGitOpsApp]:
        items, _ = await self.list_all(
            filters=[DeliveryGitOpsApp.organization_id == organization_id], limit=200,
        )
        return items


class DeliveryOperationRepository(BaseRepository[DeliveryOperation]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeliveryOperation, session)

    async def list_for_org(self, organization_id: str) -> list[DeliveryOperation]:
        stmt = (
            select(DeliveryOperation)
            .where(DeliveryOperation.organization_id == organization_id)
            .order_by(DeliveryOperation.created_at.desc())
            .limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_deployment(self, organization_id: str, deployment_id: str) -> list[DeliveryOperation]:
        stmt = (
            select(DeliveryOperation)
            .where(
                DeliveryOperation.organization_id == organization_id,
                DeliveryOperation.deployment_id == deployment_id,
            )
            .order_by(DeliveryOperation.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
