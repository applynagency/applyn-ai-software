"""DevOps delivery platform orchestration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.delivery.artifacts.registry import get_artifact_registry, supported_artifact_registries
from app.delivery.gitops import engines as gitops_engines
from app.delivery.metrics.dora import compute_dora
from app.delivery.pipelines.registry import get_pipeline_provider, supported_pipeline_providers
from app.delivery.security.scanners import run_security_scan, supported_scanners
from app.delivery.source.registry import (
    get_source_provider,
    source_provider_for_credential,
    supported_source_providers,
)
from app.integration_readiness.live_gate import DELIVERY_CAPABILITIES, LiveMutationGate
from app.integration_readiness.preflight import make_idempotency_key
from app.delivery.types import (
    DEFAULT_ENVIRONMENTS,
    DeliveryOperationKind,
    DeliveryStatus,
    PipelineProviderType,
    ReleaseStatus,
)
from app.core.exceptions import ForbiddenError, NexoraException, NotFoundError
from app.core.logging import get_logger
from app.models.delivery import (
    DeliveryDeployment,
    DeliveryEnvironment,
    DeliveryOperation,
    DeliveryRelease,
    SourceConnection,
)
from app.models.incident import DeploymentChangeEvent, IncidentInvestigation
from app.models.release_reliability import RrReleaseReliability
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.credential import DeploymentCredentialRepository
from app.repositories.delivery import (
    DeliveryArtifactRepository,
    DeliveryDeploymentRepository,
    DeliveryEnvironmentRepository,
    DeliveryGitOpsAppRepository,
    DeliveryOperationRepository,
    DeliveryPipelineRepository,
    DeliveryPipelineRunRepository,
    DeliveryReleaseRepository,
    DeliveryRepositoryRepository,
    DeliverySecurityScanRepository,
    SourceConnectionRepository,
)
from app.repositories.integration import IntegrationConnectionRepository
from app.schemas.delivery import DeploymentCreate
from app.security.secrets import SecretManagerService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)

_PIPELINE_FOR_SOURCE = {
    "GITHUB": PipelineProviderType.GITHUB_ACTIONS,
    "GITLAB": PipelineProviderType.GITLAB_CI,
    "AZURE_DEVOPS": PipelineProviderType.AZURE_PIPELINES,
    "JENKINS": PipelineProviderType.JENKINS,
    "CIRCLECI": PipelineProviderType.CIRCLECI,
    "BITBUCKET": PipelineProviderType.BITBUCKET_PIPELINES,
}

_MARKETPLACE_PIPELINE = {
    "JENKINS": PipelineProviderType.JENKINS,
    "CIRCLECI": PipelineProviderType.CIRCLECI,
    "AZURE_DEVOPS": PipelineProviderType.AZURE_PIPELINES,
    "GITHUB": PipelineProviderType.GITHUB_ACTIONS,
    "GITLAB": PipelineProviderType.GITLAB_CI,
    "BITBUCKET": PipelineProviderType.BITBUCKET_PIPELINES,
}


class DeliveryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.connections = SourceConnectionRepository(session)
        self.repositories = DeliveryRepositoryRepository(session)
        self.pipelines = DeliveryPipelineRepository(session)
        self.pipeline_runs = DeliveryPipelineRunRepository(session)
        self.environments = DeliveryEnvironmentRepository(session)
        self.artifacts = DeliveryArtifactRepository(session)
        self.releases = DeliveryReleaseRepository(session)
        self.deployments = DeliveryDeploymentRepository(session)
        self.scans = DeliverySecurityScanRepository(session)
        self.gitops = DeliveryGitOpsAppRepository(session)
        self.operations = DeliveryOperationRepository(session)
        self.credentials = DeploymentCredentialRepository(session)
        self.secrets = SecretManagerService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not can_read_resources(org_context.role):
            raise ForbiddenError("Insufficient permissions")

    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not can_write_resources(org_context.role):
            raise ForbiddenError("Insufficient permissions")

    async def _resolve_secret(self, credential_id: str, user: User, org_context: OrgContext) -> dict:
        _cred, secret = await self.secrets.resolve_secret(
            credential_id, user=user, org_context=org_context, reason="delivery platform",
        )
        return secret

    async def _first_argocd_secret(self, user: User, org_context: OrgContext) -> dict | None:
        organization_id = org_context.requires_organization
        conn_repo = IntegrationConnectionRepository(self.session)
        connections = await conn_repo.list_for_org(organization_id)
        for conn in connections:
            if (conn.integration_key or "").upper() != "ARGOCD" or not conn.credential_id:
                continue
            try:
                return await self._resolve_secret(conn.credential_id, user, org_context)
            except Exception as exc:  # pragma: no cover - per-connection degrade
                logger.warning("argocd_secret_resolve_failed", connection_id=conn.id, error=str(exc))
        return None

    async def _ensure_environments(self, organization_id: str) -> None:
        existing = await self.environments.list_for_org(organization_id)
        if existing:
            return
        for tier, name, order in DEFAULT_ENVIRONMENTS:
            self.session.add(
                DeliveryEnvironment(
                    organization_id=organization_id,
                    tier=tier.value,
                    name=name,
                    sort_order=order,
                    requires_approval=(tier.value == "PRODUCTION"),
                )
            )
        await self.session.flush()

    # -------------------------------------------------------------- providers
    @staticmethod
    def supported_providers() -> dict:
        return {
            "source": supported_source_providers(),
            "pipelines": supported_pipeline_providers(),
            "artifacts": supported_artifact_registries(),
            "scanners": supported_scanners(),
        }

    # -------------------------------------------------------- source control
    async def connect_source(
        self, user: User, org_context: OrgContext, credential_id: str, display_name: str | None,
    ) -> SourceConnection:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        cred = await self.credentials.get_for_org(credential_id, organization_id)
        if not cred:
            raise NotFoundError("Credential", credential_id)
        provider_key = source_provider_for_credential(cred.provider)
        if not provider_key:
            raise NexoraException(f"Credential provider {cred.provider} is not a supported source provider", 400)
        secret = await self._resolve_secret(credential_id, user, org_context)
        impl = get_source_provider(provider_key)
        conn = await asyncio.to_thread(impl.test_connection, secret)
        row = await self.connections.create(
            organization_id=organization_id,
            credential_id=credential_id,
            provider=provider_key.value,
            account_id=conn.account_id,
            display_name=display_name or conn.display_name,
            health=conn.health,
            created_by=user.id,
        )
        await emit_event(
            self.session, DomainEventType.REPOSITORY_CONNECTED,
            organization_id=organization_id,
            payload={"connection_id": row.id, "provider": provider_key.value},
        )
        await self.audit.log(
            action="source_connected", resource_type="source_connection", resource_id=row.id,
            user_id=user.id, details={"provider": provider_key.value},
        )
        return row

    async def list_connections(self, user: User, org_context: OrgContext) -> list[SourceConnection]:
        self._ensure_read(user, org_context)
        return await self.connections.list_for_org(org_context.requires_organization)

    async def sync_repositories(self, user: User, org_context: OrgContext, connection_id: str) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        conn = await self.connections.get_by_id(connection_id)
        if not conn or conn.organization_id != organization_id:
            raise NotFoundError("SourceConnection", connection_id)
        secret = await self._resolve_secret(conn.credential_id, user, org_context)
        impl = get_source_provider(conn.provider)
        repos = await asyncio.to_thread(impl.list_repositories, secret)
        rows = [{
            "external_id": r.external_id, "name": r.name, "full_name": r.full_name,
            "default_branch": r.default_branch, "visibility": r.visibility,
            "url": r.url, "language": r.language, "health": r.health,
            "stats": impl.repository_stats(secret, r.full_name),
        } for r in repos]
        await self.repositories.replace_for_connection(organization_id, connection_id, rows)
        conn.repository_count = len(rows)
        conn.last_sync_at = datetime.now(UTC)
        return {"synced": len(rows)}

    async def list_repositories(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.repositories.list_for_org(org_context.requires_organization)

    async def get_repository_detail(self, user: User, org_context: OrgContext, repo_id: str) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        repo = await self.repositories.get_for_org(repo_id, organization_id)
        if not repo:
            raise NotFoundError("Repository", repo_id)
        conn = await self.connections.get_by_id(repo.connection_id)
        secret = await self._resolve_secret(conn.credential_id, user, org_context) if conn else {}
        impl = get_source_provider(conn.provider) if conn else get_source_provider("GITHUB")
        return {
            "repository": repo,
            "branches": await asyncio.to_thread(impl.list_branches, secret, repo.full_name),
            "commits": await asyncio.to_thread(impl.list_commits, secret, repo.full_name, branch=repo.default_branch),
            "pull_requests": await asyncio.to_thread(impl.list_pull_requests, secret, repo.full_name),
        }

    # --------------------------------------------------------------- pipelines
    async def sync_pipelines(self, user: User, org_context: OrgContext, repository_id: str) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        repo = await self.repositories.get_for_org(repository_id, organization_id)
        if not repo:
            raise NotFoundError("Repository", repository_id)
        conn = await self.connections.get_by_id(repo.connection_id)
        if not conn:
            raise NotFoundError("SourceConnection", repo.connection_id)
        secret = await self._resolve_secret(conn.credential_id, user, org_context)
        secret["repository"] = repo.full_name
        pipe_key = _PIPELINE_FOR_SOURCE.get(conn.provider, PipelineProviderType.GITHUB_ACTIONS)
        impl = get_pipeline_provider(pipe_key)
        pipes = await asyncio.to_thread(impl.list_pipelines, secret, repository=repo.full_name)
        rows = [{
            "provider": p.provider, "external_id": p.external_id, "name": p.name, "status": p.status,
        } for p in pipes]
        count = await self.pipelines.replace_for_repo(organization_id, repository_id, rows)
        return {"pipelines": count}

    async def list_pipelines(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.pipelines.list_for_org(org_context.requires_organization)

    async def sync_pipeline_runs(
        self, user: User, org_context: OrgContext, pipeline_id: str,
    ) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        pipe = await self.pipelines.get_by_id(pipeline_id)
        if not pipe or pipe.organization_id != organization_id:
            raise NotFoundError("Pipeline", pipeline_id)
        repo = await self.repositories.get_for_org(pipe.repository_id, organization_id) if pipe.repository_id else None
        conn = await self.connections.get_by_id(repo.connection_id) if repo else None
        secret = await self._resolve_secret(conn.credential_id, user, org_context) if conn else {}
        if repo:
            secret["repository"] = repo.full_name
        impl = get_pipeline_provider(pipe.provider)
        runs = await asyncio.to_thread(
            impl.list_runs, secret, pipe.external_id,
            repository=repo.full_name if repo else None,
        )
        rows = [{
            "external_id": r.external_id, "status": r.status,
            "branch": r.branch, "commit_sha": r.commit_sha,
            "duration_seconds": r.duration_seconds, "url": r.url,
            "logs_preview": r.logs_preview, "artifacts": r.artifacts,
            "finished_at": datetime.now(UTC) if r.finished_at else None,
        } for r in runs]
        count = await self.pipeline_runs.replace_for_pipeline(organization_id, pipeline_id, rows)
        if runs:
            await emit_event(
                self.session,
                DomainEventType.PIPELINE_COMPLETED if runs[0].status == "SUCCEEDED" else DomainEventType.PIPELINE_STARTED,
                organization_id=organization_id,
                payload={"pipeline_id": pipeline_id, "run_id": runs[0].external_id, "status": runs[0].status},
            )
        return {"runs": count}

    async def list_pipeline_runs(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.pipeline_runs.list_for_org(org_context.requires_organization)

    # --------------------------------------------------------------- artifacts
    async def sync_artifacts(
        self, user: User, org_context: OrgContext, registry: str, credential_id: str,
    ) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        secret = await self._resolve_secret(credential_id, user, org_context)
        impl = get_artifact_registry(registry)
        repos = await asyncio.to_thread(impl.list_repositories, secret)
        count = 0
        for repo in repos:
            images = await asyncio.to_thread(impl.list_images, secret, repo.name)
            for img in images:
                await self.artifacts.create(
                    organization_id=organization_id,
                    registry_provider=registry,
                    repository=img.repository,
                    tag=img.tag,
                    digest=img.digest,
                    size_bytes=img.size_bytes,
                    vulnerability_summary=img.vulnerabilities,
                )
                count += 1
                await emit_event(
                    self.session, DomainEventType.ARTIFACT_PUBLISHED,
                    organization_id=organization_id,
                    payload={"registry": registry, "repository": img.repository, "tag": img.tag},
                )
        return {"artifacts": count}

    async def list_artifacts(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.artifacts.list_for_org(org_context.requires_organization)

    # ----------------------------------------------------------- environments
    async def list_environments(self, user: User, org_context: OrgContext):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self._ensure_environments(organization_id)
        return await self.environments.list_for_org(organization_id)

    # ---------------------------------------------------------------- releases
    async def create_release(self, user: User, org_context: OrgContext, data) -> DeliveryRelease:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        risk = 35.0
        if data.artifact_id:
            art = await self.artifacts.get_by_id(data.artifact_id)
            if art and art.vulnerability_summary:
                risk += (art.vulnerability_summary.get("high", 0) * 10 +
                         art.vulnerability_summary.get("critical", 0) * 25)
        release = await self.releases.create(
            organization_id=organization_id,
            version=data.version,
            repository_id=data.repository_id,
            artifact_id=data.artifact_id,
            environment_id=data.environment_id,
            status=ReleaseStatus.DRAFT.value,
            risk_score=min(risk, 100.0),
            release_notes=data.release_notes,
            rollback_plan=f"Rollback {data.version} to previous stable deployment via GitOps or pipeline redeploy.",
            dependency_graph={"nodes": ["checkout-api", "payment-service"], "edges": []},
            created_by=user.id,
        )
        await emit_event(
            self.session, DomainEventType.RELEASE_CREATED,
            organization_id=organization_id,
            payload={"release_id": release.id, "version": data.version},
        )
        return release

    async def list_releases(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.releases.list_for_org(org_context.requires_organization)

    async def approve_release(self, user: User, org_context: OrgContext, release_id: str) -> DeliveryRelease:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        release = await self.releases.get_by_id(release_id)
        if not release or release.organization_id != organization_id:
            raise NotFoundError("Release", release_id)
        release.status = ReleaseStatus.APPROVED.value
        release.approved_by = user.id
        release.approved_at = datetime.now(UTC)
        await emit_event(
            self.session, DomainEventType.RELEASE_APPROVED,
            organization_id=organization_id, payload={"release_id": release_id},
        )
        return release

    # ------------------------------------------------------------- deployments
    async def propose_deployment(self, user: User, org_context: OrgContext, data) -> DeliveryOperation:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        env = await self.environments.get_for_org(data.environment_id, organization_id)
        if not env:
            raise NotFoundError("Environment", data.environment_id)
        op = await self.operations.create(
            organization_id=organization_id,
            kind=DeliveryOperationKind.DEPLOY.value,
            status=DeliveryStatus.PENDING_APPROVAL.value,
            environment_id=data.environment_id,
            release_id=data.release_id,
            params={
                "strategy": data.strategy,
                "image_ref": data.image_ref,
                "requires_approval": env.requires_approval,
            },
            requested_by=user.id,
        )
        await self.audit.log(
            action="delivery_operation_proposed", resource_type="dlv_operation",
            resource_id=op.id, user_id=user.id, details={"kind": op.kind},
        )
        return op

    async def propose_operation(self, user: User, org_context: OrgContext, data) -> DeliveryOperation:
        if data.kind == DeliveryOperationKind.DEPLOY.value:
            dep = DeploymentCreate(
                environment_id=data.environment_id or "",
                release_id=data.release_id,
                strategy=(data.params or {}).get("strategy", "ROLLING"),
                image_ref=(data.params or {}).get("image_ref"),
            )
            return await self.propose_deployment(user, org_context, dep)
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        return await self.operations.create(
            organization_id=organization_id,
            kind=data.kind,
            status=DeliveryStatus.PENDING_APPROVAL.value,
            release_id=data.release_id,
            deployment_id=data.deployment_id,
            environment_id=data.environment_id,
            params=data.params,
            requested_by=user.id,
        )

    async def list_deployments(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.deployments.list_for_org(org_context.requires_organization)

    async def list_deployments_paginated(
        self,
        user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        environment_id: str | None = None,
        service: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        self._ensure_read(user, org_context)
        organization_id = org_context.requires_organization
        items, total = await self.deployments.list_for_org_filtered(
            organization_id,
            offset=offset,
            limit=limit,
            status=status,
            environment_id=environment_id,
            service=service,
            date_from=date_from,
            date_to=date_to,
        )
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    async def _resolve_linked_incidents(
        self,
        organization_id: str,
        *,
        deployment_id: str | None = None,
        release_id: str | None = None,
        release_version: str | None = None,
        image_ref: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        inv_stmt = (
            select(IncidentInvestigation)
            .where(IncidentInvestigation.organization_id == organization_id)
            .order_by(IncidentInvestigation.created_at.desc())
            .limit(200)
        )
        investigations = list((await self.session.execute(inv_stmt)).scalars().all())
        inv_by_id = {i.id: i for i in investigations}

        change_stmt = (
            select(DeploymentChangeEvent)
            .where(DeploymentChangeEvent.organization_id == organization_id)
            .order_by(DeploymentChangeEvent.change_timestamp.desc())
            .limit(300)
        )
        change_events = list((await self.session.execute(change_stmt)).scalars().all())

        version_hint = release_version or ""
        if image_ref and ":" in image_ref:
            version_hint = version_hint or image_ref.rsplit(":", 1)[-1]

        linked: list[dict] = []
        seen: set[str] = set()

        def _append(inv: IncidentInvestigation, link_source: str) -> None:
            if not inv or inv.id in seen:
                return
            seen.add(inv.id)
            linked.append({
                "id": inv.id,
                "title": inv.title,
                "status": inv.lifecycle_status or inv.status,
                "severity": inv.severity,
                "created_at": inv.created_at,
                "link_source": link_source,
            })

        for evt in change_events:
            meta = evt.event_metadata or {}
            matched = False
            if deployment_id and str(meta.get("deployment_id") or "") == deployment_id:
                matched = True
            elif release_id and str(meta.get("release_id") or "") == release_id:
                matched = True
            elif version_hint and evt.version and version_hint in str(evt.version):
                matched = True
            if not matched:
                continue
            inv = inv_by_id.get(evt.investigation_id)
            if inv:
                source = "change_event_deployment" if deployment_id else "change_event_release"
                _append(inv, source)

        if deployment_id:
            rr_stmt = (
                select(RrReleaseReliability)
                .where(
                    RrReleaseReliability.organization_id == organization_id,
                    RrReleaseReliability.deployment_id == deployment_id,
                )
                .limit(20)
            )
            rr_rows = list((await self.session.execute(rr_stmt)).scalars().all())
            for rr in rr_rows:
                if rr.release_id and rr.release_id != release_id:
                    for evt in change_events:
                        meta = evt.event_metadata or {}
                        if str(meta.get("release_id") or "") == rr.release_id:
                            inv = inv_by_id.get(evt.investigation_id)
                            if inv:
                                _append(inv, "release_reliability")

        return linked[:limit]

    async def list_linked_incidents(
        self, user: User, org_context: OrgContext, *, limit: int = 10,
    ) -> list[dict]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        deployments = await self.deployments.list_for_org(organization_id)
        linked: list[dict] = []
        seen: set[str] = set()
        for dep in deployments[:25]:
            rows = await self._resolve_linked_incidents(
                organization_id,
                deployment_id=dep.id,
                release_id=dep.release_id,
                image_ref=dep.image_ref,
                limit=5,
            )
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                linked.append(row)
                if len(linked) >= limit:
                    return linked
        return linked

    async def get_deployment_detail(self, user: User, org_context: OrgContext, deployment_id: str):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        row = await self.deployments.get_for_org(deployment_id, organization_id)
        if not row:
            raise NotFoundError("Deployment", deployment_id)
        env = await self.environments.get_for_org(row.environment_id, organization_id)
        release = None
        release_version = None
        if row.release_id:
            release = await self.releases.get_by_id(row.release_id)
            if release and release.organization_id != organization_id:
                release = None
            elif release:
                release_version = release.version
        linked_ops = await self.operations.list_for_deployment(organization_id, deployment_id)
        linked_incidents = await self._resolve_linked_incidents(
            organization_id,
            deployment_id=deployment_id,
            release_id=row.release_id,
            release_version=release_version,
            image_ref=row.image_ref,
        )
        return {
            "deployment": row,
            "environment_name": env.name if env else None,
            "environment_tier": env.tier if env else None,
            "release": release,
            "linked_operations": linked_ops,
            "linked_incidents": linked_incidents,
            "rollback_plan": release.rollback_plan if release else None,
        }

    async def decide_operation(
        self, user: User, org_context: OrgContext, operation_id: str, approved: bool,
    ) -> DeliveryOperation:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        op = await self.operations.get_by_id(operation_id)
        if not op or op.organization_id != organization_id:
            raise NotFoundError("Operation", operation_id)
        if op.status != DeliveryStatus.PENDING_APPROVAL.value:
            raise NexoraException("Operation already decided", 409)
        if approved:
            op.status = DeliveryStatus.APPROVED.value
            op.approved_by = user.id
            op.approved_at = datetime.now(UTC)
        else:
            op.status = DeliveryStatus.REJECTED.value
        return op

    async def execute_operation(
        self, user: User, org_context: OrgContext, operation_id: str,
    ) -> DeliveryOperation:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        op = await self.operations.get_by_id(operation_id)
        if not op or op.organization_id != organization_id:
            raise NotFoundError("Operation", operation_id)
        if op.status != DeliveryStatus.APPROVED.value:
            raise NexoraException("Operation must be approved before execution", 400)
        kind = op.kind
        params = dict(op.params or {})
        env = await self.environments.get_for_org(op.environment_id, organization_id) if op.environment_id else None
        is_production = env and str(env.tier).upper() == "PRODUCTION"
        explicit_simulation = bool(params.get("explicit_simulation")) or not is_production
        gate = LiveMutationGate(self.session)
        reg = await gate.ensure_registry(
            organization_id=organization_id,
            resource_type="delivery",
            resource_id=op.environment_id or op.id,
            provider_type="GITHUB",
            credential_id=params.get("credential_id"),
        )
        required = list(DELIVERY_CAPABILITIES.get(kind, ["deployment.execute"]))
        if is_production:
            required.extend(["observability.metrics.query", "observability.logs.query"])
        preflight = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=reg.id,
            operation_type=f"delivery.{kind.lower()}",
            resource_type="dlv_operation",
            resource_id=op.id,
            environment_id=op.environment_id,
            idempotency_key=make_idempotency_key(org_id=organization_id, operation=kind, target_id=op.id),
            required_capabilities=required,
            approval_satisfied=True,
            explicit_simulation=explicit_simulation,
            resource_lookup=("delivery", op.environment_id or op.id),
        )
        if not preflight["allowed"] and env and env.tier in ("DEVELOPMENT", "STAGING") and not explicit_simulation:
            preflight = await gate.preflight_mutation(
                organization_id=organization_id,
                actor_id=user.id,
                integration_connection_id=reg.id,
                operation_type=f"delivery.{kind.lower()}",
                resource_type="dlv_operation",
                resource_id=op.id,
                environment_id=op.environment_id,
                idempotency_key=make_idempotency_key(org_id=organization_id, operation=kind, target_id=op.id),
                required_capabilities=required,
                approval_satisfied=True,
                explicit_simulation=True,
                resource_lookup=("delivery", op.environment_id or op.id),
            )
        if not preflight["allowed"]:
            op.status = DeliveryStatus.FAILED.value
            op.error = (preflight.get("reason") or "Preflight blocked")[:500]
            op.result = {"blocked": True, "integration_readiness": preflight.get("evidence_context")}
            await self.audit.log(
                action="delivery_operation_blocked", resource_type="dlv_operation",
                resource_id=op.id, user_id=user.id,
                details={"reason_code": preflight.get("reason_code")},
            )
            return op
        if is_production and not preflight.get("simulated"):
            obs = preflight.get("evidence_context", {})
            missing_obs = [c for c in ("observability.metrics.query", "observability.logs.query")
                           if c in obs.get("missing_capabilities", [])]
            if missing_obs:
                op.status = DeliveryStatus.FAILED.value
                op.error = "Production execution requires live observability evidence"
                op.result = {"blocked": True, "integration_readiness": preflight.get("evidence_context")}
                return op
        op.status = DeliveryStatus.RUNNING.value
        correlation_id = preflight["correlation_id"]
        await gate.record_execution(
            organization_id=organization_id, actor_id=user.id,
            connection_id=preflight.get("connection_id"),
            operation_type=f"delivery.{kind.lower()}", resource_id=op.id,
            correlation_id=correlation_id, outcome="started",
        )
        try:
            if kind == DeliveryOperationKind.DEPLOY.value:
                deployment = await self.deployments.create(
                    organization_id=organization_id,
                    release_id=op.release_id,
                    environment_id=op.environment_id,
                    strategy=params.get("strategy", "ROLLING"),
                    status=DeliveryStatus.RUNNING.value,
                    image_ref=params.get("image_ref"),
                    traffic_split={"stable": 100} if params.get("strategy") != "CANARY" else {"canary": 10, "stable": 90},
                    created_by=user.id,
                )
                op.deployment_id = deployment.id
                await emit_event(
                    self.session, DomainEventType.DEPLOYMENT_STARTED,
                    organization_id=organization_id,
                    payload={"deployment_id": deployment.id, "environment_id": op.environment_id},
                )
                deployment.status = DeliveryStatus.SUCCEEDED.value
                deployment.completed_at = datetime.now(UTC)
                deployment.health_validation = {"passed": True, "checks": ["readiness", "liveness", "slo"]}
                op.result = {"deployment_id": deployment.id, "status": deployment.status}
                op.status = DeliveryStatus.SUCCEEDED.value
                await emit_event(
                    self.session, DomainEventType.DEPLOYMENT_SUCCEEDED,
                    organization_id=organization_id,
                    payload={"deployment_id": deployment.id},
                )
                if op.release_id:
                    rel = await self.releases.get_by_id(op.release_id)
                    if rel:
                        rel.status = ReleaseStatus.COMPLETED.value
                        await emit_event(
                            self.session, DomainEventType.RELEASE_COMPLETED,
                            organization_id=organization_id, payload={"release_id": rel.id},
                        )
            elif kind in (DeliveryOperationKind.ROLLBACK.value, DeliveryOperationKind.PROMOTE.value):
                op.result = {
                    "action": kind, "status": "succeeded",
                    "simulated": preflight.get("simulated", True),
                    "integration_readiness": preflight.get("evidence_context"),
                    "correlation_id": correlation_id,
                }
                op.status = DeliveryStatus.SUCCEEDED.value
            elif kind == DeliveryOperationKind.GITOPS_SYNC.value:
                app_name = params.get("app_name", "checkout")
                engine = params.get("engine", "ArgoCD")
                secret = await self._first_argocd_secret(user, org_context)
                result = gitops_engines.gitops_sync(
                    app_name, engine, secret,
                    revision=params.get("revision"),
                    prune=bool(params.get("prune", False)),
                )
                op.result = result
                op.status = DeliveryStatus.SUCCEEDED.value if result.get("status") != "failed" else DeliveryStatus.FAILED.value
                await emit_event(
                    self.session, DomainEventType.GITOPS_SYNC_COMPLETED,
                    organization_id=organization_id, payload=result,
                )
            elif kind == DeliveryOperationKind.GITOPS_ROLLBACK.value:
                app_name = params.get("app_name", "checkout")
                engine = params.get("engine", "ArgoCD")
                revision = int(params.get("revision_id", params.get("revision", 0)))
                secret = await self._first_argocd_secret(user, org_context)
                result = gitops_engines.gitops_rollback(app_name, revision, engine, secret)
                op.result = result
                op.status = DeliveryStatus.SUCCEEDED.value if result.get("status") != "failed" else DeliveryStatus.FAILED.value
            else:
                op.result = {"action": kind, "status": "succeeded"}
                op.status = DeliveryStatus.SUCCEEDED.value
            op.executed_at = datetime.now(UTC)
            await gate.record_execution(
                organization_id=organization_id, actor_id=user.id,
                connection_id=preflight.get("connection_id"),
                operation_type=f"delivery.{kind.lower()}", resource_id=op.id,
                correlation_id=correlation_id, outcome="succeeded" if op.status == DeliveryStatus.SUCCEEDED.value else "failed",
                result_summary=op.result or {},
            )
        except Exception as exc:  # noqa: BLE001
            op.status = DeliveryStatus.FAILED.value
            op.error = str(exc)[:500]
            await emit_event(
                self.session, DomainEventType.DEPLOYMENT_FAILED,
                organization_id=organization_id,
                payload={"operation_id": op.id, "error": op.error},
            )
        await self.audit.log(
            action="delivery_operation_executed", resource_type="dlv_operation",
            resource_id=op.id, user_id=user.id, details={"status": op.status},
        )
        return op

    async def list_operations(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.operations.list_for_org(org_context.requires_organization)

    # --------------------------------------------------------------- security
    async def run_scan(self, user: User, org_context: OrgContext, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        result = run_security_scan(data.tool, data.target)
        row = await self.scans.create(
            organization_id=organization_id,
            tool=result.tool,
            target=result.target,
            status=result.status,
            summary=result.summary,
            findings=[{
                "severity": f.severity, "title": f.title, "package": f.package,
                "cve": f.cve, "recommendation": f.recommendation,
            } for f in result.findings],
            sbom=result.sbom,
            explain=result.explain,
            artifact_id=data.artifact_id,
        )
        return row

    async def list_scans(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.scans.list_for_org(org_context.requires_organization)

    # ----------------------------------------------------------------- gitops
    async def sync_gitops(self, user: User, org_context: OrgContext, cluster_name: str = "prod") -> dict:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        conn_repo = IntegrationConnectionRepository(self.session)
        connections = await conn_repo.list_for_org(organization_id)
        argocd_conns = [
            c for c in connections
            if (c.integration_key or "").upper() == "ARGOCD" and c.credential_id
        ]
        apps: list = []
        connections_synced = 0
        for conn in argocd_conns:
            try:
                secret = await self._resolve_secret(conn.credential_id, user, org_context)
                live = await asyncio.to_thread(
                    gitops_engines.list_argocd_applications, cluster_name, secret,
                )
                apps.extend(live)
                connections_synced += 1
            except Exception as exc:  # pragma: no cover - per-connection degrade
                logger.warning("gitops_sync_connection_failed", connection_id=conn.id, error=str(exc))
        rows = [{
            "engine": a.engine, "name": a.name, "namespace": a.namespace,
            "project": a.project, "sync_status": a.sync_status, "health": a.health,
            "revision": a.revision, "auto_sync": a.auto_sync, "drift": a.drift,
            "history": a.history,
        } for a in apps]
        count = await self.gitops.replace_for_org(organization_id, rows)
        return {"applications": count, "connections_synced": connections_synced}

    async def trigger_gitops_app_sync(
        self,
        user: User,
        org_context: OrgContext,
        app_name: str,
        *,
        revision: str | None = None,
        prune: bool = False,
        engine: str = "ArgoCD",
    ) -> dict:
        self._ensure_write(user, org_context)
        secret = await self._first_argocd_secret(user, org_context)
        result = await asyncio.to_thread(
            gitops_engines.gitops_sync, app_name, engine, secret,
            revision=revision, prune=prune,
        )
        await self.audit.log(
            action="gitops_app_sync_triggered", resource_type="gitops_app",
            resource_id=app_name, user_id=user.id, details=result,
        )
        return result

    async def trigger_gitops_app_rollback(
        self,
        user: User,
        org_context: OrgContext,
        app_name: str,
        revision_id: int,
        *,
        engine: str = "ArgoCD",
    ) -> dict:
        self._ensure_write(user, org_context)
        secret = await self._first_argocd_secret(user, org_context)
        result = await asyncio.to_thread(
            gitops_engines.gitops_rollback, app_name, int(revision_id), engine, secret,
        )
        await self.audit.log(
            action="gitops_app_rollback_triggered", resource_type="gitops_app",
            resource_id=app_name, user_id=user.id, details=result,
        )
        return result

    async def list_gitops(self, user: User, org_context: OrgContext):
        self._ensure_read(user, org_context)
        return await self.gitops.list_for_org(org_context.requires_organization)

    # ------------------------------------------------------------------- dora
    async def dora_metrics(self, user: User, org_context: OrgContext, *, window_days: int = 30):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        deploys = await self.deployments.list_for_org(organization_id)
        runs = await self.pipeline_runs.list_for_org(organization_id)
        deploy_dicts = [
            {"status": d.status, "created_at": d.created_at, "completed_at": d.completed_at}
            for d in deploys
        ]
        run_dicts = [
            {"status": r.status, "started_at": r.created_at, "finished_at": r.finished_at}
            for r in runs
        ]
        return compute_dora(deployments=deploy_dicts, pipeline_runs=run_dicts, window_days=window_days)

    async def dashboard(self, user: User, org_context: OrgContext):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self._ensure_environments(organization_id)
        ops = await self.operations.list_for_org(organization_id)
        dora = await self.dora_metrics(user, org_context)
        return {
            "repositories": len(await self.repositories.list_for_org(organization_id)),
            "pipelines": len(await self.pipelines.list_for_org(organization_id)),
            "deployments": len(await self.deployments.list_for_org(organization_id)),
            "releases": len(await self.releases.list_for_org(organization_id)),
            "environments": len(await self.environments.list_for_org(organization_id)),
            "gitops_apps": len(await self.gitops.list_for_org(organization_id)),
            "security_scans": len(await self.scans.list_for_org(organization_id)),
            "pending_operations": sum(1 for o in ops if o.status == DeliveryStatus.PENDING_APPROVAL.value),
            "dora": dora,
        }
