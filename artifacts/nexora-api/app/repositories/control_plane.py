"""Repositories for the control plane."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.control_plane import (
    CloudAccount,
    CloudInventoryResource,
    CloudSyncRun,
    ClusterDiscoveryRun,
    ClusterPolicyFinding,
    ClusterResource,
    ControlPlaneCostSnapshot,
    ControlPlaneOperation,
    KubernetesCluster,
)
from app.repositories.base import BaseRepository


class CloudAccountRepository(BaseRepository[CloudAccount]):
    def __init__(self, session: AsyncSession):
        super().__init__(CloudAccount, session)

    async def list_for_org(self, organization_id: str) -> list[CloudAccount]:
        items, _ = await self.list_all(
            filters=[CloudAccount.organization_id == organization_id, CloudAccount.is_active.is_(True)],
            limit=500,
        )
        return items


class KubernetesClusterRepository(BaseRepository[KubernetesCluster]):
    def __init__(self, session: AsyncSession):
        super().__init__(KubernetesCluster, session)

    async def list_for_org(self, organization_id: str) -> list[KubernetesCluster]:
        items, _ = await self.list_all(
            filters=[KubernetesCluster.organization_id == organization_id, KubernetesCluster.is_active.is_(True)],
            limit=500,
        )
        return items

    async def get_for_org(self, cluster_id: str, organization_id: str) -> KubernetesCluster | None:
        stmt = select(KubernetesCluster).where(
            KubernetesCluster.id == cluster_id,
            KubernetesCluster.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ControlPlaneOperationRepository(BaseRepository[ControlPlaneOperation]):
    def __init__(self, session: AsyncSession):
        super().__init__(ControlPlaneOperation, session)

    async def list_for_org(self, organization_id: str, *, limit: int = 100) -> list[ControlPlaneOperation]:
        stmt = (
            select(ControlPlaneOperation)
            .where(ControlPlaneOperation.organization_id == organization_id)
            .order_by(ControlPlaneOperation.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ClusterResourceRepository(BaseRepository[ClusterResource]):
    def __init__(self, session: AsyncSession):
        super().__init__(ClusterResource, session)

    async def replace_for_cluster(
        self, organization_id: str, cluster_id: str, resources: list[dict],
    ) -> int:
        await self.session.execute(
            delete(ClusterResource).where(
                ClusterResource.organization_id == organization_id,
                ClusterResource.cluster_id == cluster_id,
            )
        )
        count = 0
        for r in resources:
            await self.create(
                organization_id=organization_id, cluster_id=cluster_id, **r,
            )
            count += 1
        return count

    async def list_for_cluster(
        self, organization_id: str, cluster_id: str, *, kind: str | None = None,
        namespace: str | None = None, limit: int = 500,
    ) -> list[ClusterResource]:
        filters = [
            ClusterResource.organization_id == organization_id,
            ClusterResource.cluster_id == cluster_id,
        ]
        if kind:
            filters.append(ClusterResource.kind == kind)
        if namespace:
            filters.append(ClusterResource.namespace == namespace)
        items, _ = await self.list_all(filters=filters, limit=limit)
        return items


class CloudInventoryRepository(BaseRepository[CloudInventoryResource]):
    def __init__(self, session: AsyncSession):
        super().__init__(CloudInventoryResource, session)

    async def replace_for_account(
        self, organization_id: str, cloud_account_id: str, items: list[dict],
    ) -> int:
        await self.session.execute(
            delete(CloudInventoryResource).where(
                CloudInventoryResource.organization_id == organization_id,
                CloudInventoryResource.cloud_account_id == cloud_account_id,
            )
        )
        for row in items:
            await self.create(organization_id=organization_id, cloud_account_id=cloud_account_id, **row)
        return len(items)

    async def unified_inventory(self, organization_id: str, *, limit: int = 1000) -> list[CloudInventoryResource]:
        items, _ = await self.list_all(
            filters=[CloudInventoryResource.organization_id == organization_id],
            limit=limit,
        )
        return items
