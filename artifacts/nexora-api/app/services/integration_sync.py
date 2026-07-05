"""Sync live data from marketplace integrations into Delivery / Discovery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException, NotFoundError
from app.delivery.gitops import engines as gitops_engines
from app.delivery.pipelines.registry import get_pipeline_provider
from app.delivery.types import PipelineProviderType
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.delivery import (
    DeliveryGitOpsAppRepository,
    DeliveryPipelineRepository,
    DeliveryPipelineRunRepository,
)
from app.repositories.integration import IntegrationConnectionRepository
from app.security.secrets import SecretManagerService
from app.services.integration_capabilities import supports_gitops_sync, supports_pipeline_sync
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

_PIPELINE_MAP = {
    "JENKINS": PipelineProviderType.JENKINS,
    "CIRCLECI": PipelineProviderType.CIRCLECI,
    "AZURE_DEVOPS": PipelineProviderType.AZURE_PIPELINES,
    "GITHUB": PipelineProviderType.GITHUB_ACTIONS,
    "GITLAB": PipelineProviderType.GITLAB_CI,
    "BITBUCKET": PipelineProviderType.BITBUCKET_PIPELINES,
}


class IntegrationSyncService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.connections = IntegrationConnectionRepository(session)
        self.pipelines = DeliveryPipelineRepository(session)
        self.pipeline_runs = DeliveryPipelineRunRepository(session)
        self.gitops = DeliveryGitOpsAppRepository(session)
        self.secrets = SecretManagerService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def sync_connection(
        self, user: User, org_context: OrgContext, connection_id: str, *, sync_runs: bool = True,
    ) -> dict:
        organization_id = self._ensure_write(user, org_context)
        connection = await self.connections.get_for_org(connection_id, organization_id)
        if not connection:
            raise NotFoundError("IntegrationConnection", connection_id)

        key = (connection.integration_key or "").upper()
        if supports_gitops_sync(key):
            return await self._sync_gitops(user, org_context, connection, key)
        if not supports_pipeline_sync(key):
            raise NexoraException(f"{key} does not support pipeline or gitops sync.", 400)

        if not connection.credential_id:
            raise NexoraException("No credential attached to this connection.", 400)

        _, secret = await self.secrets.resolve_secret(
            connection.credential_id, user=user, org_context=org_context,
            reason="integration pipeline sync",
        )
        pipe_type = _PIPELINE_MAP.get(key)
        if not pipe_type:
            raise NexoraException(f"No pipeline provider for {key}.", 400)

        impl = get_pipeline_provider(pipe_type)
        pipes = await asyncio.to_thread(impl.list_pipelines, secret)
        rows = [{
            "provider": p.provider,
            "external_id": p.external_id,
            "name": p.name,
            "status": p.status,
        } for p in pipes]
        count = await self.pipelines.replace_for_integration(organization_id, connection_id, rows)

        run_count = 0
        if sync_runs and pipes:
            stored = await self.pipelines.list_for_org(organization_id)
            linked = [p for p in stored if p.integration_connection_id == connection_id]
            for pipe_row in linked[:15]:
                runs = await asyncio.to_thread(
                    impl.list_runs, secret, pipe_row.external_id, limit=10,
                )
                run_rows = [{
                    "external_id": r.external_id,
                    "status": r.status,
                    "branch": r.branch,
                    "commit_sha": r.commit_sha,
                    "duration_seconds": r.duration_seconds,
                    "url": r.url,
                    "logs_preview": r.logs_preview,
                    "artifacts": r.artifacts,
                    "finished_at": datetime.now(UTC) if r.finished_at else None,
                } for r in runs]
                run_count += await self.pipeline_runs.replace_for_pipeline(
                    organization_id, pipe_row.id, run_rows,
                )

        now = datetime.now(UTC)
        await self.connections.update(connection, last_sync_at=now)
        await self.audit.log(
            action="integration_synced",
            resource_type="integration_connection",
            resource_id=connection.id,
            user_id=user.id,
            details={"pipelines": count, "runs": run_count, "integration": key},
        )
        return {
            "connection_id": connection_id,
            "integration_key": key,
            "pipelines_synced": count,
            "runs_synced": run_count,
            "synced_at": now.isoformat(),
        }

    async def _sync_gitops(
        self, user: User, org_context: OrgContext, connection, key: str,
    ) -> dict:
        organization_id = self._ensure_write(user, org_context)
        if not connection.credential_id:
            raise NexoraException("No credential attached to this connection.", 400)
        _, secret = await self.secrets.resolve_secret(
            connection.credential_id, user=user, org_context=org_context,
            reason="integration gitops sync",
        )
        apps = await asyncio.to_thread(
            gitops_engines.list_flux_applications if key == "FLUX" else gitops_engines.list_argocd_applications,
            "prod", secret,
        )
        rows = [{
            "engine": a.engine, "name": a.name, "namespace": a.namespace,
            "project": a.project, "sync_status": a.sync_status, "health": a.health,
            "revision": a.revision, "auto_sync": a.auto_sync, "drift": a.drift,
            "history": a.history,
        } for a in apps]
        count = await self.gitops.replace_for_org(organization_id, rows)
        now = datetime.now(UTC)
        await self.connections.update(connection, last_sync_at=now)
        await self.audit.log(
            action="integration_gitops_synced",
            resource_type="integration_connection",
            resource_id=connection.id,
            user_id=user.id,
            details={"applications": count, "integration": key},
        )
        return {
            "connection_id": connection.id,
            "integration_key": key,
            "applications_synced": count,
            "synced_at": now.isoformat(),
        }
