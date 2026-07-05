"""Sprint 35A — credential & secret-access repositories."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import DeploymentCredential, SecretAccessAudit
from app.repositories.base import BaseRepository


class DeploymentCredentialRepository(BaseRepository[DeploymentCredential]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeploymentCredential, session)

    async def get_for_org(
        self, credential_id: str, organization_id: str
    ) -> DeploymentCredential | None:
        stmt = select(DeploymentCredential).where(
            DeploymentCredential.id == credential_id,
            DeploymentCredential.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, offset: int = 0, limit: int = 100
    ) -> tuple[list[DeploymentCredential], int]:
        base = select(DeploymentCredential).where(
            DeploymentCredential.organization_id == organization_id
        )
        total = (
            await self.session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(DeploymentCredential.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


class SecretAccessAuditRepository(BaseRepository[SecretAccessAudit]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecretAccessAudit, session)

    async def record(
        self,
        *,
        organization_id: str,
        event: str,
        credential_id: str | None = None,
        actor_user_id: str | None = None,
        reason: str | None = None,
        deployment_id: str | None = None,
    ) -> SecretAccessAudit:
        return await self.create(
            organization_id=organization_id,
            event=event,
            credential_id=credential_id,
            actor_user_id=actor_user_id,
            reason=reason,
            deployment_id=deployment_id,
        )

    async def list_for_org(
        self, organization_id: str, *, offset: int = 0, limit: int = 200
    ) -> tuple[list[SecretAccessAudit], int]:
        base = select(SecretAccessAudit).where(
            SecretAccessAudit.organization_id == organization_id
        )
        total = (
            await self.session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(SecretAccessAudit.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)
