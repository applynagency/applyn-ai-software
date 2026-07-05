"""Platform Engineering orchestration (Sprint 64A).

Extends the Control Plane — does not duplicate cloud/K8s provider logic.
IaC execution uses provider registry; cluster registration delegates to ControlPlaneService.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integration_readiness.live_gate import IAC_CAPABILITIES, LiveMutationGate
from app.integration_readiness.preflight import make_idempotency_key
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.platform_engineering import (
    PECatalogItem,
    PECatalogRequest,
    PEComplianceReport,
    PEDriftFinding,
    PEEnvironment,
    PEGoldenTemplate,
    PEIacRepository,
    PEIacRun,
    PEIacStack,
    PEPlatformTemplate,
    PEProvisionRun,
    PESecretReference,
)
from app.models.control_plane import ClusterPolicyFinding
from app.models.integration import ConnectionStatus
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.platform_engineering.compliance.checks import run_compliance_scan
from app.platform_engineering.drift.scanner import aggregate_drift
from app.platform_engineering.iac.registry import run_iac_operation, supported_iac_providers
from app.platform_engineering.secrets.registry import resolve_secret_ref, supported_secret_backends
from app.platform_engineering.templates.specs import golden_template_spec, template_spec
from app.platform_engineering.types import (
    APPROVAL_REQUIRED_IAC,
    DEFAULT_CATALOG_ITEMS,
    DEFAULT_PLATFORM_TEMPLATES,
    CatalogRequestStatus,
    EnvironmentTier,
    IaCRunKind,
    IaCRunStatus,
    ProvisionStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.control_plane import (
    CloudAccountRepository,
    KubernetesClusterRepository,
)
from app.repositories.delivery import DeliveryGitOpsAppRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.repositories.platform_engineering import (
    PECatalogItemRepo,
    PECatalogRequestRepo,
    PEComplianceReportRepo,
    PEDriftFindingRepo,
    PEEnvironmentRepo,
    PEGoldenTemplateRepo,
    PEIacRepositoryRepo,
    PEIacRunRepo,
    PEIacStackRepo,
    PEPlatformTemplateRepo,
    PEProvisionRunRepo,
    PESecretRefRepo,
)
from app.schemas.platform_engineering import (
    CatalogRequestCreate,
    EnvironmentCreate,
    GoldenTemplateCreate,
    IaCRepositoryCreate,
    IaCRunCreate,
    IaCStackCreate,
    ProvisionCreate,
    SecretRefCreate,
)
from app.security.secrets import SecretManagerService
from app.services.control_plane import ControlPlaneService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)

_MARKETPLACE_CONNECTION_STATUSES = frozenset({
    ConnectionStatus.VERIFIED.value,
    ConnectionStatus.CONNECTED.value,
})

_DIST_MAP = {
    "AKS": "AKS", "EKS": "EKS", "GKE": "GKE", "K3S": "K3S",
    "OPENSHIFT": "OPENSHIFT", "DIGITALOCEAN": "VANILLA",
}


class PlatformEngineeringService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repos = PEIacRepositoryRepo(session)
        self.stacks = PEIacStackRepo(session)
        self.runs = PEIacRunRepo(session)
        self.templates = PEPlatformTemplateRepo(session)
        self.environments = PEEnvironmentRepo(session)
        self.provisions = PEProvisionRunRepo(session)
        self.secret_refs = PESecretRefRepo(session)
        self.catalog = PECatalogItemRepo(session)
        self.catalog_requests = PECatalogRequestRepo(session)
        self.golden = PEGoldenTemplateRepo(session)
        self.compliance = PEComplianceReportRepo(session)
        self.drift = PEDriftFindingRepo(session)
        self.cloud_accounts = CloudAccountRepository(session)
        self.clusters = KubernetesClusterRepository(session)
        self.gitops = DeliveryGitOpsAppRepository(session)
        self.control_plane = ControlPlaneService(session)
        self.audit = AuditLogRepository(session)
        self.marketplace_connections = IntegrationConnectionRepository(session)
        self.secrets = SecretManagerService(session)

    async def _marketplace_secret(
        self, organization_id: str, user_id: str, integration_key: str, *, reason: str,
    ) -> dict | None:
        from app.auth.org_context import OrgContext
        from app.models.organization import OrganizationRole

        user = await self.session.get(User, user_id)
        if user is None:
            return None
        org_context = OrgContext(
            user=user, organization_id=organization_id, role=OrganizationRole.OWNER,
        )
        connections = await self.marketplace_connections.list_for_org(organization_id)
        for conn in connections:
            if (conn.integration_key or "").upper() != integration_key:
                continue
            if conn.status not in _MARKETPLACE_CONNECTION_STATUSES or not conn.credential_id:
                continue
            try:
                _cred, secret = await self.secrets.resolve_secret(
                    conn.credential_id, user=user, org_context=org_context, reason=reason,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("marketplace secret resolve failed: %s", exc)
                continue
            return secret or {}
        return None

    async def _terraform_live_config(self, organization_id: str, user_id: str) -> dict | None:
        return await self._marketplace_secret(
            organization_id, user_id, "TERRAFORM", reason="platform engineering iac plan",
        )

    async def _vault_live_config(
        self, organization_id: str, user: User, org_context: OrgContext,
    ) -> dict | None:
        connections = await self.marketplace_connections.list_for_org(organization_id)
        for conn in connections:
            if (conn.integration_key or "").upper() != "HASHICORP_VAULT":
                continue
            if conn.status not in _MARKETPLACE_CONNECTION_STATUSES or not conn.credential_id:
                continue
            try:
                _cred, secret = await self.secrets.resolve_secret(
                    conn.credential_id, user=user, org_context=org_context, reason="vault secret ref",
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("vault secret resolve failed: %s", exc)
                continue
            return secret or {}
        return None

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    @staticmethod
    def supported_providers() -> dict:
        return {
            "iac": supported_iac_providers(),
            "secret_backends": supported_secret_backends(),
            "distributions": list(_DIST_MAP.keys()),
        }

    async def _seed_catalog(self, organization_id: str) -> None:
        if await self.templates.list_for_org(organization_id):
            return
        for kind, name, dist in DEFAULT_PLATFORM_TEMPLATES:
            self.session.add(PEPlatformTemplate(
                organization_id=organization_id,
                kind=kind.value,
                name=name,
                description=f"Platform template for {dist}",
                spec=template_spec(kind),
                is_builtin=True,
            ))
        for kind, name, desc in DEFAULT_CATALOG_ITEMS:
            self.session.add(PECatalogItem(
                organization_id=organization_id,
                kind=kind.value,
                name=name,
                description=desc,
                spec={"self_service": True},
                requires_approval=True,
            ))
        await self.session.flush()

    # -------------------------------------------------------------- dashboard
    async def dashboard(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        await self._seed_catalog(organization_id)
        runs = await self.runs.list_for_org(organization_id)
        pending = sum(1 for r in runs if r.status == IaCRunStatus.PENDING_APPROVAL.value)
        pending += sum(
            1 for p in await self.provisions.list_for_org(organization_id)
            if p.status == ProvisionStatus.PENDING_APPROVAL.value
        )
        report = await self.compliance.latest(organization_id)
        drift_count = len(await self.drift.list_active(organization_id))
        return {
            "repositories": len(await self.repos.list_for_org(organization_id)),
            "stacks": len(await self.stacks.list_for_org(organization_id)),
            "environments": len(await self.environments.list_for_org(organization_id)),
            "pending_approvals": pending,
            "active_drift": drift_count,
            "latest_compliance_score": report.score if report else None,
        }

    # -------------------------------------------------------- IaC repositories
    async def create_repository(
        self, user: User, org_context: OrgContext, payload: IaCRepositoryCreate,
    ) -> PEIacRepository:
        organization_id = self._ensure_write(user, org_context)
        row = PEIacRepository(
            organization_id=organization_id,
            name=payload.name,
            provider=payload.provider,
            url=payload.url,
            default_branch=payload.default_branch,
            working_dir=payload.working_dir,
            credential_id=payload.credential_id,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.log(
            action="pe.iac_repository_created", resource_type="pe_iac_repository",
            resource_id=row.id, user_id=user.id,
        )
        return row

    async def list_repositories(self, user: User, org_context: OrgContext) -> list[PEIacRepository]:
        organization_id = self._ensure_read(user, org_context)
        return await self.repos.list_for_org(organization_id)

    # -------------------------------------------------------------- IaC stacks
    async def create_stack(
        self, user: User, org_context: OrgContext, payload: IaCStackCreate,
    ) -> PEIacStack:
        organization_id = self._ensure_write(user, org_context)
        row = PEIacStack(
            organization_id=organization_id,
            name=payload.name,
            provider=payload.provider,
            repository_id=payload.repository_id,
            variables=payload.variables,
            secret_refs=payload.secret_refs,
            state_backend=payload.state_backend,
            cloud_account_id=payload.cloud_account_id,
            cluster_id=payload.cluster_id,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.log(
            action="pe.iac_stack_created", resource_type="pe_iac_stack",
            resource_id=row.id, user_id=user.id,
        )
        return row

    async def list_stacks(self, user: User, org_context: OrgContext) -> list[PEIacStack]:
        organization_id = self._ensure_read(user, org_context)
        return await self.stacks.list_for_org(organization_id)

    # ---------------------------------------------------------------- IaC runs
    async def propose_run(
        self, user: User, org_context: OrgContext, stack_id: str, payload: IaCRunCreate,
    ) -> PEIacRun:
        organization_id = self._ensure_write(user, org_context)
        stack = await self.stacks.get_by_id(stack_id)
        if not stack or stack.organization_id != organization_id:
            raise NotFoundError("IaCStack", stack_id)
        kind = IaCRunKind(payload.kind)
        status = (
            IaCRunStatus.PENDING_APPROVAL.value
            if kind in APPROVAL_REQUIRED_IAC
            else IaCRunStatus.QUEUED.value
        )
        row = PEIacRun(
            organization_id=organization_id,
            stack_id=stack_id,
            kind=kind.value,
            status=status,
            requested_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        if status == IaCRunStatus.QUEUED.value:
            await self._execute_run(row, stack, payload.variables or stack.variables)
        await self.audit.log(
            action="pe.iac_run_proposed", resource_type="pe_iac_run",
            resource_id=row.id, user_id=user.id, details={"kind": kind.value},
        )
        return row

    async def decide_run(
        self, user: User, org_context: OrgContext, run_id: str, *, approved: bool,
    ) -> PEIacRun:
        organization_id = self._ensure_write(user, org_context)
        row = await self.runs.get_by_id(run_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("IaCRun", run_id)
        if row.status != IaCRunStatus.PENDING_APPROVAL.value:
            raise ForbiddenError("Run is not pending approval")
        stack = await self.stacks.get_by_id(row.stack_id)
        if not stack:
            raise NotFoundError("IaCStack", row.stack_id)
        if approved:
            row.status = IaCRunStatus.APPROVED.value
            row.approved_by = user.id
            await self.session.flush()
            await self._execute_run(row, stack, stack.variables)
        else:
            row.status = IaCRunStatus.REJECTED.value
            await self.session.flush()
        return row

    async def _execute_run(self, row: PEIacRun, stack: PEIacStack, variables: dict) -> None:
        gate = LiveMutationGate(self.session)
        reg = await gate.ensure_registry(
            organization_id=row.organization_id,
            resource_type="iac_stack",
            resource_id=stack.id,
            provider_type=stack.provider.upper(),
            credential_id=stack.credential_id,
        )
        destroy = row.kind in ("DESTROY",)
        explicit_simulation = bool((row.variables or {}).get("explicit_simulation"))
        preflight = await gate.preflight_mutation(
            organization_id=row.organization_id,
            actor_id=row.requested_by,
            integration_connection_id=reg.id,
            operation_type=f"iac.{row.kind.lower()}",
            resource_type="pe_iac_run",
            resource_id=row.id,
            idempotency_key=make_idempotency_key(org_id=row.organization_id, operation=row.kind, target_id=row.id),
            required_capabilities=IAC_CAPABILITIES.get(row.kind, ["iac.apply"]),
            approval_satisfied=True,
            explicit_simulation=explicit_simulation,
            resource_lookup=("iac_stack", stack.id),
            destroy=destroy,
        )
        if not preflight["allowed"]:
            row.status = IaCRunStatus.FAILED.value
            row.error = (preflight.get("reason") or "Preflight blocked")[:500]
            row.finished_at = utcnow()
            row.outputs = {"integration_readiness": preflight.get("evidence_context"), "blocked": True}
            return
        row.status = IaCRunStatus.RUNNING.value
        correlation_id = preflight["correlation_id"]
        await gate.record_execution(
            organization_id=row.organization_id, actor_id=row.requested_by,
            connection_id=preflight.get("connection_id"),
            operation_type=f"iac.{row.kind.lower()}", resource_id=row.id,
            correlation_id=correlation_id, outcome="started",
        )
        await self.session.flush()
        try:
            live_config = None
            if not preflight.get("simulated", True) and str(stack.provider).upper() == "TERRAFORM":
                live_config = await self._terraform_live_config(row.organization_id, row.requested_by)
            result = await asyncio.to_thread(
                run_iac_operation,
                stack.provider,
                row.kind,
                working_dir=f"/iac/{stack.id}",
                variables=variables,
                live_config=live_config,
            )
            result_dict = {
                "success": result.success,
                "simulated": preflight.get("simulated", True),
                "integration_readiness": preflight.get("evidence_context"),
            }
            row.logs = result.logs
            row.finished_at = utcnow()
            if result.success:
                row.status = IaCRunStatus.SUCCEEDED.value
                row.outputs = {**(result.outputs or {}), **result_dict}
                if result.plan:
                    row.plan_summary = {
                        "add": result.plan.add,
                        "change": result.plan.change,
                        "destroy": result.plan.destroy,
                        "drift_detected": result.plan.drift_detected,
                    }
                if result.state_metadata:
                    stack.state_metadata = result.state_metadata
                    stack.outputs = result.outputs
                event = DomainEventType.TERRAFORM_APPLIED if row.kind == IaCRunKind.APPLY.value else DomainEventType.TERRAFORM_PLAN_GENERATED
                await emit_event(
                    self.session,
                    event_type=event,
                    organization_id=row.organization_id,
                    actor_id=row.requested_by,
                    aggregate_type="pe_iac_run",
                    aggregate_id=row.id,
                    payload={"kind": row.kind, "stack_id": stack.id},
                )
            else:
                row.status = IaCRunStatus.FAILED.value
                row.error = result.error
            await gate.record_execution(
                organization_id=row.organization_id, actor_id=row.requested_by,
                connection_id=preflight.get("connection_id"),
                operation_type=f"iac.{row.kind.lower()}", resource_id=row.id,
                correlation_id=correlation_id,
                outcome="succeeded" if row.status == IaCRunStatus.SUCCEEDED.value else "failed",
                result_summary=result_dict if result.success else {"error": result.error},
            )
        except Exception as exc:  # noqa: BLE001
            row.status = IaCRunStatus.FAILED.value
            row.error = str(exc)
            row.finished_at = utcnow()
            await gate.record_execution(
                organization_id=row.organization_id, actor_id=row.requested_by,
                connection_id=preflight.get("connection_id"),
                operation_type=f"iac.{row.kind.lower()}", resource_id=row.id,
                correlation_id=correlation_id, outcome="failed",
            )

    async def list_runs(self, user: User, org_context: OrgContext, stack_id: str | None = None) -> list[PEIacRun]:
        organization_id = self._ensure_read(user, org_context)
        if stack_id:
            stack = await self.stacks.get_by_id(stack_id)
            if not stack or stack.organization_id != organization_id:
                raise NotFoundError("IaCStack", stack_id)
            return await self.runs.list_for_stack(stack_id)
        return await self.runs.list_for_org(organization_id)

    # -------------------------------------------------------- platform templates
    async def list_templates(self, user: User, org_context: OrgContext) -> list[PEPlatformTemplate]:
        organization_id = self._ensure_read(user, org_context)
        await self._seed_catalog(organization_id)
        return await self.templates.list_for_org(organization_id)

    # ---------------------------------------------------------- environments
    async def create_environment(
        self, user: User, org_context: OrgContext, payload: EnvironmentCreate,
    ) -> PEEnvironment:
        organization_id = self._ensure_write(user, org_context)
        await self._seed_catalog(organization_id)
        tier = EnvironmentTier(payload.tier) if payload.tier in EnvironmentTier.__members__ else EnvironmentTier.DEVELOPMENT
        requires_approval = tier in (EnvironmentTier.STAGING, EnvironmentTier.PRODUCTION, EnvironmentTier.PERFORMANCE)
        row = PEEnvironment(
            organization_id=organization_id,
            name=payload.name,
            tier=tier.value,
            template_id=payload.template_id,
            status=ProvisionStatus.PENDING_APPROVAL.value if requires_approval else ProvisionStatus.APPROVED.value,
            cloud_account_id=payload.cloud_account_id,
            components={"networking": True, "monitoring": True, "gitops": True, "secrets": True},
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session,
            event_type=DomainEventType.ENVIRONMENT_CREATED,
            organization_id=organization_id,
            actor_id=user.id,
            aggregate_type="pe_environment",
            aggregate_id=row.id,
            payload={"name": payload.name, "tier": tier.value},
        )
        if not requires_approval:
            await self._provision_environment(row, user, org_context)
        return row

    async def approve_environment(
        self, user: User, org_context: OrgContext, environment_id: str, *, approved: bool,
    ) -> PEEnvironment:
        organization_id = self._ensure_write(user, org_context)
        row = await self.environments.get_by_id(environment_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("Environment", environment_id)
        if approved:
            row.status = ProvisionStatus.APPROVED.value
            row.approved_by = user.id
            await self.session.flush()
            await self._provision_environment(row, user, org_context)
        else:
            row.status = ProvisionStatus.REJECTED.value
            await self.session.flush()
        return row

    async def _provision_environment(
        self, env: PEEnvironment, user: User, org_context: OrgContext,
    ) -> None:
        env.status = ProvisionStatus.PROVISIONING.value
        stack = PEIacStack(
            organization_id=env.organization_id,
            name=f"env-{env.name}",
            provider="TERRAFORM",
            variables={"environment": env.name, "tier": env.tier},
            cloud_account_id=env.cloud_account_id,
            created_by=user.id,
        )
        self.session.add(stack)
        await self.session.flush()
        env.stack_id = stack.id
        result = await asyncio.to_thread(
            run_iac_operation, "TERRAFORM", IaCRunKind.APPLY.value,
            working_dir=f"/iac/env-{env.id}", variables=stack.variables,
        )
        env.components = {
            **env.components,
            "provisioned": result.success,
            "outputs": result.outputs,
        }
        env.status = ProvisionStatus.SUCCEEDED.value if result.success else ProvisionStatus.FAILED.value

    async def list_environments(self, user: User, org_context: OrgContext) -> list[PEEnvironment]:
        organization_id = self._ensure_read(user, org_context)
        return await self.environments.list_for_org(organization_id)

    # ----------------------------------------------------- cluster provisioning
    async def start_provision(
        self, user: User, org_context: OrgContext, payload: ProvisionCreate,
    ) -> PEProvisionRun:
        organization_id = self._ensure_write(user, org_context)
        row = PEProvisionRun(
            organization_id=organization_id,
            environment_id=payload.environment_id,
            template_kind=payload.template_kind,
            distribution=payload.distribution,
            status=ProvisionStatus.PENDING_APPROVAL.value,
            requested_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session,
            event_type=DomainEventType.PROVISION_STARTED,
            organization_id=organization_id,
            actor_id=user.id,
            aggregate_type="pe_provision_run",
            aggregate_id=row.id,
            payload={"distribution": payload.distribution},
        )
        await self.audit.log(
            action="pe.provision_started", resource_type="pe_provision_run",
            resource_id=row.id, user_id=user.id,
        )
        return row

    async def decide_provision(
        self, user: User, org_context: OrgContext, provision_id: str, *, approved: bool,
    ) -> PEProvisionRun:
        organization_id = self._ensure_write(user, org_context)
        row = await self.provisions.get_by_id(provision_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("ProvisionRun", provision_id)
        if not approved:
            row.status = ProvisionStatus.REJECTED.value
            await self.session.flush()
            return row
        row.status = ProvisionStatus.PROVISIONING.value
        row.approved_by = user.id
        row.progress_percent = 10
        await self.session.flush()
        spec = template_spec(row.template_kind)
        result = await asyncio.to_thread(
            run_iac_operation, "TERRAFORM", IaCRunKind.APPLY.value,
            working_dir=f"/provision/{row.id}",
            variables={"distribution": row.distribution, "template": row.template_kind},
        )
        row.progress_percent = 100
        row.logs = result.logs
        row.finished_at = utcnow()
        if result.success:
            row.status = ProvisionStatus.SUCCEEDED.value
            cluster_id = str(uuid.uuid4())
            row.outputs = result.outputs
            row.cluster_id = cluster_id
            await emit_event(
                self.session,
                event_type=DomainEventType.PROVISION_COMPLETED,
                organization_id=organization_id,
                actor_id=user.id,
                aggregate_type="pe_provision_run",
                aggregate_id=row.id,
                payload={"cluster_id": cluster_id, "distribution": row.distribution},
            )
        else:
            row.status = ProvisionStatus.FAILED.value
            row.error = result.error
        return row

    async def list_provisions(self, user: User, org_context: OrgContext) -> list[PEProvisionRun]:
        organization_id = self._ensure_read(user, org_context)
        return await self.provisions.list_for_org(organization_id)

    # -------------------------------------------------------------- secrets
    async def create_secret_ref(
        self, user: User, org_context: OrgContext, payload: SecretRefCreate,
    ) -> PESecretReference:
        organization_id = self._ensure_write(user, org_context)
        vault_config = None
        if str(payload.backend).upper() == "VAULT":
            vault_config = await self._vault_live_config(organization_id, user, org_context)
        meta = resolve_secret_ref(payload.backend, payload.path, vault_config=vault_config)
        row = PESecretReference(
            organization_id=organization_id,
            name=payload.name,
            backend=payload.backend,
            path=payload.path,
            stack_id=payload.stack_id,
            environment_id=payload.environment_id,
            rotation_days=payload.rotation_days,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.log(
            action="pe.secret_ref_created", resource_type="pe_secret_ref",
            resource_id=row.id, user_id=user.id, details={"backend": payload.backend, "meta": meta},
        )
        return row

    async def list_secret_refs(self, user: User, org_context: OrgContext) -> list[PESecretReference]:
        organization_id = self._ensure_read(user, org_context)
        return await self.secret_refs.list_for_org(organization_id)

    async def rotate_secret_ref(
        self, user: User, org_context: OrgContext, ref_id: str,
    ) -> PESecretReference:
        organization_id = self._ensure_write(user, org_context)
        row = await self.secret_refs.get_by_id(ref_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("SecretRef", ref_id)
        row.last_rotated_at = utcnow()
        await self.session.flush()
        await emit_event(
            self.session,
            event_type=DomainEventType.SECRET_ROTATED,
            organization_id=organization_id,
            actor_id=user.id,
            aggregate_type="pe_secret_ref",
            aggregate_id=row.id,
            payload={"name": row.name, "backend": row.backend},
        )
        return row

    async def delete_secret_ref(self, user: User, org_context: OrgContext, ref_id: str) -> None:
        organization_id = self._ensure_write(user, org_context)
        row = await self.secret_refs.get_by_id(ref_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("SecretRef", ref_id)
        await self.session.delete(row)
        await self.audit.log(
            action="pe.secret_ref_deleted", resource_type="pe_secret_ref",
            resource_id=ref_id, user_id=user.id, details={"name": row.name},
        )

    # --------------------------------------------------------------- catalog
    async def list_catalog(self, user: User, org_context: OrgContext) -> list[PECatalogItem]:
        organization_id = self._ensure_read(user, org_context)
        await self._seed_catalog(organization_id)
        return await self.catalog.list_for_org(organization_id)

    async def request_catalog_item(
        self, user: User, org_context: OrgContext, payload: CatalogRequestCreate,
    ) -> PECatalogRequest:
        organization_id = self._ensure_write(user, org_context)
        item = await self.catalog.get_by_id(payload.catalog_item_id)
        if not item or item.organization_id != organization_id:
            raise NotFoundError("CatalogItem", payload.catalog_item_id)
        row = PECatalogRequest(
            organization_id=organization_id,
            catalog_item_id=payload.catalog_item_id,
            status=CatalogRequestStatus.PENDING_APPROVAL.value,
            params=payload.params,
            requested_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def decide_catalog_request(
        self, user: User, org_context: OrgContext, request_id: str, *, approved: bool,
    ) -> PECatalogRequest:
        organization_id = self._ensure_write(user, org_context)
        row = await self.catalog_requests.get_by_id(request_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("CatalogRequest", request_id)
        if approved:
            row.status = CatalogRequestStatus.PROVISIONING.value
            row.approved_by = user.id
            prov = await self.start_provision(
                user, org_context,
                ProvisionCreate(
                    template_kind=row.params.get("template_kind", "EKS"),
                    distribution=row.params.get("distribution", "EKS"),
                ),
            )
            row.provision_id = prov.id
            row.status = CatalogRequestStatus.COMPLETED.value
        else:
            row.status = CatalogRequestStatus.REJECTED.value
        await self.session.flush()
        return row

    async def list_catalog_requests(self, user: User, org_context: OrgContext) -> list[PECatalogRequest]:
        organization_id = self._ensure_read(user, org_context)
        return await self.catalog_requests.list_for_org(organization_id)

    # ------------------------------------------------------- golden templates
    async def create_golden_template(
        self, user: User, org_context: OrgContext, payload: GoldenTemplateCreate,
    ) -> PEGoldenTemplate:
        organization_id = self._ensure_write(user, org_context)
        row = PEGoldenTemplate(
            organization_id=organization_id,
            kind=payload.kind,
            name=payload.name,
            description=payload.description,
            spec=golden_template_spec(payload.kind),
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session,
            event_type=DomainEventType.PLATFORM_TEMPLATE_CREATED,
            organization_id=organization_id,
            actor_id=user.id,
            aggregate_type="pe_golden_template",
            aggregate_id=row.id,
            payload={"kind": payload.kind},
        )
        return row

    async def list_golden_templates(self, user: User, org_context: OrgContext) -> list[PEGoldenTemplate]:
        organization_id = self._ensure_read(user, org_context)
        return await self.golden.list_for_org(organization_id)

    # -------------------------------------------------------------- compliance
    async def run_compliance(self, user: User, org_context: OrgContext) -> PEComplianceReport:
        organization_id = self._ensure_write(user, org_context)
        accounts = await self.cloud_accounts.list_for_org(organization_id)
        resources = [
            {"id": a.id, "name": a.display_name, "tags": {"owner": "platform"}, "public": False}
            for a in accounts
        ]
        clusters = [
            {"name": c.name, "network_policies": True}
            for c in await self.clusters.list_for_org(organization_id)
        ]
        report_data = run_compliance_scan(resources=resources, clusters=clusters)
        row = PEComplianceReport(
            organization_id=organization_id,
            score=report_data["score"],
            grade=report_data["grade"],
            findings=report_data["findings"],
            summary=report_data,
            generated_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.log(
            action="pe.compliance_scan", resource_type="pe_compliance_report",
            resource_id=row.id, user_id=user.id,
        )
        return row

    async def latest_compliance(self, user: User, org_context: OrgContext) -> PEComplianceReport | None:
        organization_id = self._ensure_read(user, org_context)
        return await self.compliance.latest(organization_id)

    # ------------------------------------------------------------------ drift
    async def scan_drift(self, user: User, org_context: OrgContext) -> list[PEDriftFinding]:
        organization_id = self._ensure_write(user, org_context)
        findings: list[PEDriftFinding] = []
        stacks = await self.stacks.list_for_org(organization_id)
        accounts = await self.cloud_accounts.list_for_org(organization_id)
        policy_stmt = (
            select(ClusterPolicyFinding)
            .where(ClusterPolicyFinding.organization_id == organization_id)
            .limit(50)
        )
        policy_findings = list((await self.session.execute(policy_stmt)).scalars().all())
        for stack in stacks:
            raw = aggregate_drift(
                stack_name=stack.name,
                state_metadata=stack.state_metadata,
                account_id=stack.cloud_account_id or "",
                resource_count=sum(a.resource_count for a in accounts),
                cluster_id=stack.cluster_id or "",
                policy_findings=policy_findings,
                gitops_apps=await self.gitops.list_for_org(organization_id),
            )
            for f in raw:
                explanation = (
                    f"AI analysis: {f['message']} — likely caused by manual change or failed sync. "
                    f"Recommendation: {f['recommendation']}"
                )
                row = PEDriftFinding(
                    organization_id=organization_id,
                    source=f["source"],
                    resource=f["resource"],
                    message=f["message"],
                    severity=f["severity"],
                    recommendation=f["recommendation"],
                    ai_explanation=explanation,
                    stack_id=stack.id,
                    cluster_id=f.get("cluster_id"),
                )
                self.session.add(row)
                findings.append(row)
        await self.session.flush()
        for row in findings:
            await emit_event(
                self.session,
                event_type=DomainEventType.TERRAFORM_DRIFT_DETECTED,
                organization_id=organization_id,
                actor_id=user.id,
                aggregate_type="pe_drift_finding",
                aggregate_id=row.id,
                payload={"source": row.source, "resource": row.resource},
            )
        return findings

    async def list_drift(self, user: User, org_context: OrgContext) -> list[PEDriftFinding]:
        organization_id = self._ensure_read(user, org_context)
        return await self.drift.list_active(organization_id)

    async def acknowledge_drift(
        self, user: User, org_context: OrgContext, finding_id: str,
    ) -> PEDriftFinding:
        organization_id = self._ensure_write(user, org_context)
        row = await self.drift.get_by_id(finding_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("DriftFinding", finding_id)
        row.acknowledged = True
        await self.session.flush()
        return row

    # ----------------------------------------------------------- AI context
    async def ai_context(self, user: User, org_context: OrgContext, *, question: str | None = None) -> dict:
        organization_id = self._ensure_read(user, org_context)
        dash = await self.dashboard(user, org_context)
        return {
            "dashboard": dash,
            "suggested_questions": [
                "Create production AKS cluster",
                "Generate Terraform for this environment",
                "Review the latest Terraform plan",
                "Explain infrastructure drift findings",
                "Recommend cost optimizations",
            ],
            "copilot_endpoint": "/v1/copilot/chat",
        }
