import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.deployment import DeploymentAgent
from app.auth.org_context import OrgContext
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.deployment.azure_container_apps import azure_deployment_configured
from app.deployment.deployer import DeploymentDeployer
from app.deployment.markdown import output_to_markdown
from app.deployment.validator import APPROVED_ASSEMBLY_STATUSES, DeploymentValidator
from app.models.approval import ApprovalRunStatus, WorkflowApprovalStatus
from app.models.deployment import DeploymentProvider, DeploymentRun, DeploymentStatus
from app.models.fullstack_assembly import FullstackAssemblyRunStatus
from app.models.user import User
from app.repositories.approval import ApprovalRunRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.deployment import (
    DeploymentArtifactRepository,
    DeploymentLogRepository,
    DeploymentRunRepository,
)
from app.repositories.fullstack_assembly import FullstackAssemblyRunRepository
from app.repositories.project import ProjectRepository
from app.schemas.deployment import (
    DeploymentArtifactResponse,
    DeploymentLogListResponse,
    DeploymentLogResponse,
    DeploymentRunListResponse,
    DeploymentRunRequest,
    DeploymentRunResponse,
)
from app.security.secrets import SecretManagerService
from app.tenancy.guards import get_deployment_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class DeploymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = DeploymentRunRepository(session)
        self.artifact_repo = DeploymentArtifactRepository(session)
        self.log_repo = DeploymentLogRepository(session)
        self.approval_run_repo = ApprovalRunRepository(session)
        self.fsa_run_repo = FullstackAssemblyRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.secret_manager = SecretManagerService(session)
        self.validator = DeploymentValidator()
        self.deployer = DeploymentDeployer()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: DeploymentRun) -> DeploymentRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = DeploymentArtifactResponse.model_validate(latest)
        return DeploymentRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            approval_run_id=run.approval_run_id,
            fullstack_assembly_run_id=run.fullstack_assembly_run_id,
            status=run.status,
            deployment_provider=run.deployment_provider,
            live_url=run.live_url,
            environment=run.environment,
            rollback_available=run.rollback_available,
            rollback_metadata=run.rollback_metadata,
            created_by=run.created_by,
            created_at=run.created_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            validation_score=run.validation_score,
            deployer_version=run.deployer_version,
            artifact=artifact,
        )

    async def _resolve_approval_output(
        self,
        *,
        requirement_id: str,
        approval_run_id: str | None,
    ) -> tuple[str, dict, str | None]:
        if approval_run_id:
            approval_run = await self.approval_run_repo.get_with_artifact(approval_run_id)
            if not approval_run or approval_run.requirement_id != requirement_id:
                raise NotFoundError("ApprovalRun", approval_run_id or "")
            if approval_run.status != ApprovalRunStatus.COMPLETED:
                raise ValidationError("Approval run is not completed")
        else:
            items, _ = await self.approval_run_repo.list_by_requirement(requirement_id, limit=100)
            approved = [
                run
                for run in items
                if run.status == ApprovalRunStatus.COMPLETED
                and run.approval_status
                in (
                    WorkflowApprovalStatus.APPROVED.value,
                    WorkflowApprovalStatus.DEPLOYED.value,
                )
                and run.artifacts
            ]
            if not approved:
                under_review = [
                    run
                    for run in items
                    if run.status == ApprovalRunStatus.COMPLETED
                    and run.approval_status == WorkflowApprovalStatus.UNDER_REVIEW.value
                ]
                if under_review:
                    raise ValidationError(
                        "Deployment requires approval_status APPROVED "
                        f"(current: {under_review[0].approval_status})"
                    )
                raise ValidationError(
                    "No human-approved approval run found. "
                    "Approve via /v1/approval/{artifact_id}/approve first."
                )
            approval_run = approved[0]

        if approval_run.approval_status not in (
            WorkflowApprovalStatus.APPROVED.value,
            WorkflowApprovalStatus.DEPLOYED.value,
        ):
            raise ValidationError(
                f"Deployment requires approval_status APPROVED (current: {approval_run.approval_status})"
            )

        if not approval_run.artifacts:
            raise ValidationError("Approval run has no output")

        latest = sorted(approval_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return approval_run.id, latest.artifact_json, approval_run.fullstack_assembly_run_id

    async def _resolve_fullstack_assembly_output(
        self,
        *,
        requirement_id: str,
        fullstack_assembly_run_id: str | None,
    ) -> tuple[str, dict]:
        if fullstack_assembly_run_id:
            fsa_run = await self.fsa_run_repo.get_with_artifact(fullstack_assembly_run_id)
            if not fsa_run or fsa_run.requirement_id != requirement_id:
                raise NotFoundError("FullstackAssemblyRun", fullstack_assembly_run_id or "")
            if fsa_run.status != FullstackAssemblyRunStatus.COMPLETED:
                raise ValidationError("Full Stack Assembly run is not completed")
        else:
            raise ValidationError("Full Stack Assembly run reference is required for deployment")

        if not fsa_run.artifacts:
            raise ValidationError("Full Stack Assembly run has no output")

        assembly_status = fsa_run.assembly_status
        if assembly_status not in APPROVED_ASSEMBLY_STATUSES:
            raise ValidationError(
                f"Full Stack Assembly must be approved (current: {assembly_status})"
            )

        latest = sorted(fsa_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return fsa_run.id, latest.artifact_json

    async def _persist_logs(self, run_id: str, logs: list) -> None:
        for entry in logs:
            if isinstance(entry, dict):
                await self.log_repo.create(
                    run_id=run_id,
                    level=entry.get("level", "INFO"),
                    message=entry.get("message", str(entry)),
                    log_metadata=entry.get("metadata"),
                )
            else:
                await self.log_repo.create(run_id=run_id, level="INFO", message=str(entry))

    def _should_run_async(self, deployment_provider: str) -> bool:
        """Background execution is used only for real Azure deployments.

        When Azure is not configured the deterministic simulated provider runs
        inline (fast, synchronous) so existing behaviour and tests are preserved.
        """
        return (
            deployment_provider == DeploymentProvider.AZURE.value
            and azure_deployment_configured()
        )

    async def run(
        self,
        data: DeploymentRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> DeploymentRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        deployment_target = (
            data.deployment_target.model_dump() if data.deployment_target else None
        )

        # Sprint 35A: resolve a stored encrypted credential into the transient
        # deployment target. The decrypted secret is held in memory only and is
        # never persisted on the run.
        credential = None
        if data.credential_id:
            credential, secret = await self.secret_manager.resolve_secret(
                data.credential_id,
                user=current_user,
                org_context=org_context,
                reason="deployment execution",
                audit=False,
            )
            deployment_target = {**(deployment_target or {}), **secret}

        if data.deployment_provider == DeploymentProvider.VM.value and not deployment_target:
            raise ValidationError(
                "deployment_target (host, username, private_key) or a credential_id "
                "is required for VM deployments"
            )
        if data.deployment_provider == DeploymentProvider.KUBERNETES.value and not (
            deployment_target and deployment_target.get("kubeconfig")
        ):
            raise ValidationError(
                "deployment_target.kubeconfig or a Kubernetes credential_id is "
                "required for Kubernetes deployments"
            )

        deployment_run, ctx = await self._prepare_deployment(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            user=current_user,
            approval_run_id=data.approval_run_id,
            deployment_provider=data.deployment_provider,
            environment=data.environment,
            deployment_target=deployment_target,
        )

        if credential is not None:
            await self.secret_manager.record_usage(
                credential,
                user=current_user,
                org_context=org_context,
                deployment_id=deployment_run.id,
            )

        if self._should_run_async(data.deployment_provider):
            # Persist the queued run before backgrounding so the worker session
            # can read it, then run the long build/deploy off the request thread.
            run_id = deployment_run.id
            await self.session.commit()
            asyncio.create_task(_run_deployment_background(run_id, ctx))
            queued = await self.run_repo.get_with_artifact(run_id)
            return self._to_response(queued)

        await self._perform_deployment(
            run_id=deployment_run.id, ctx=ctx, raise_on_error=True
        )
        run = await self.run_repo.get_with_artifact(deployment_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        approval_run_id: str | None = None,
        deployment_provider: str = "AZURE",
        environment: str = "production",
        deployment_target: dict | None = None,
    ) -> tuple[DeploymentRun, dict]:
        """Synchronous end-to-end deployment (prepare + perform).

        Retained for the lifecycle/synchronous callers and tests. Real async
        backgrounding is handled in :meth:`run`.
        """
        deployment_run, ctx = await self._prepare_deployment(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            user=user,
            approval_run_id=approval_run_id,
            deployment_provider=deployment_provider,
            environment=environment,
            deployment_target=deployment_target,
        )
        artifact_payload = await self._perform_deployment(
            run_id=deployment_run.id, ctx=ctx, raise_on_error=True
        )
        refreshed = await self.run_repo.get_with_artifact(deployment_run.id)
        return refreshed, artifact_payload or {}

    async def _prepare_deployment(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        user: User,
        approval_run_id: str | None,
        deployment_provider: str,
        environment: str,
        deployment_target: dict | None = None,
    ) -> tuple[DeploymentRun, dict]:
        """Resolve gates, create the run record, and return the deploy context.

        Gate validation runs synchronously so the caller receives immediate
        feedback (e.g. "not approved") before any background work is scheduled.
        """
        approval_id, approval_output, fsa_run_id = await self._resolve_approval_output(
            requirement_id=requirement_id,
            approval_run_id=approval_run_id,
        )
        fsa_run_id, fsa_output = await self._resolve_fullstack_assembly_output(
            requirement_id=requirement_id,
            fullstack_assembly_run_id=fsa_run_id,
        )

        deployer_version = self.deployer.get_deployer_version()
        manifest = fsa_output.get("application_manifest") or {}
        app_name = manifest.get("name", "application")

        deployment_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            approval_run_id=approval_id,
            fullstack_assembly_run_id=fsa_run_id,
            status=DeploymentStatus.PENDING.value,
            deployment_provider=deployment_provider,
            environment=environment,
            created_by=user.id,
            deployer_version=deployer_version,
            rollback_available=False,
        )

        await self.audit_repo.log(
            action="deployment_started",
            resource_type="deployment_run",
            resource_id=deployment_run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "approval_run_id": approval_id,
                "fullstack_assembly_run_id": fsa_run_id,
                "deployment_provider": deployment_provider,
                "environment": environment,
            },
        )

        await self.run_repo.update(deployment_run, status=DeploymentStatus.QUEUED.value)

        ctx = {
            "approval_id": approval_id,
            "approval_output": approval_output,
            "fsa_output": fsa_output,
            "app_name": app_name,
            "deployer_version": deployer_version,
            "deployment_provider": deployment_provider,
            "environment": environment,
            "user_id": user.id,
            # In-memory only; never persisted (carries the SSH private key for VM).
            "deployment_target": deployment_target,
        }
        return deployment_run, ctx

    async def _perform_deployment(
        self,
        *,
        run_id: str,
        ctx: dict,
        raise_on_error: bool,
    ) -> dict | None:
        """Run the provider deploy, validate, and finalise the run record.

        When ``raise_on_error`` is True (synchronous path) failures propagate to
        the caller. When False (background path) failures are persisted as a
        FAILED run and swallowed so the caller can poll status.
        """
        deployment_run = await self.run_repo.get_with_artifact(run_id)
        approval_output = ctx["approval_output"]
        fsa_output = ctx["fsa_output"]
        app_name = ctx["app_name"]
        environment = ctx["environment"]
        deployment_provider = ctx["deployment_provider"]
        deployer_version = ctx["deployer_version"]
        approval_id = ctx["approval_id"]
        user_id = ctx["user_id"]
        deployment_target = ctx.get("deployment_target")

        await self.run_repo.update(deployment_run, status=DeploymentStatus.DEPLOYING.value)

        try:
            agent = DeploymentAgent()
            output = await agent.run(
                fullstack_assembly_output=fsa_output,
                approval_output=approval_output,
                app_name=app_name,
                environment=environment,
                deployment_provider=deployment_provider,
                deployment_target=deployment_target,
            )
        except AgentError as exc:
            await self.run_repo.update(
                deployment_run,
                status=DeploymentStatus.FAILED.value,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="deployment_failed",
                resource_type="deployment_run",
                resource_id=deployment_run.id,
                user_id=user_id,
                details={"error": str(exc)},
                status="failure",
            )
            if raise_on_error:
                raise
            return None

        validation = self.validator.validate(
            output,
            approval_approved=True,
            assembly_approved=True,
        )
        if not validation.is_valid:
            await self.run_repo.update(
                deployment_run,
                status=DeploymentStatus.FAILED.value,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="deployment_failed",
                resource_type="deployment_run",
                resource_id=deployment_run.id,
                user_id=user_id,
                details={"error": validation.errors},
                status="failure",
            )
            if raise_on_error:
                raise ValidationError(
                    f"Deployment output failed validation (score: {validation.score})"
                )
            return None

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

        meta = output.deployment_metadata or {}
        rollback_metadata = {
            "provider": output.deployment_provider,
            "previous_revision": meta.get("previous_revision", "rev-001"),
            "target_revision": meta.get("target_revision", "rev-002"),
            "app_name": app_name,
            "container_app_name": meta.get("container_app_name"),
            # VM-specific (non-secret) metadata; None for Azure.
            "server_ip": meta.get("server_ip"),
            "deployment_path": meta.get("deployment_path"),
            "container_name": meta.get("container_name"),
            "health_url": meta.get("health_url"),
            "previous_release": meta.get("previous_release"),
            # Kubernetes-specific (non-secret) metadata; None for others.
            "cluster": meta.get("cluster"),
            "namespace": meta.get("namespace"),
            "deployment_name": meta.get("deployment_name"),
            "service_name": meta.get("service_name"),
            "ingress_url": meta.get("ingress_url"),
        }

        await self.artifact_repo.create(
            run_id=deployment_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            deployment_status=output.deployment_status,
            deployment_provider=output.deployment_provider,
            live_url=output.live_url,
            validation_score=validation.score,
            deployer_version=deployer_version,
        )

        await self._persist_logs(deployment_run.id, output.deployment_logs)

        # The real provider reports terminal failure (e.g. failed health check)
        # by returning a FAILED output rather than raising; honour that here.
        if output.deployment_status != DeploymentStatus.DEPLOYED.value:
            error_message = (
                output.deployment_metadata.get("error")
                or "Deployment did not reach a healthy state"
            )
            await self.run_repo.update(
                deployment_run,
                status=DeploymentStatus.FAILED.value,
                completed_at=datetime.now(UTC),
                error_message=error_message,
                validation_score=validation.score,
            )
            await self.audit_repo.log(
                action="deployment_failed",
                resource_type="deployment_run",
                resource_id=deployment_run.id,
                user_id=user_id,
                details={"error": error_message, "deployment_status": output.deployment_status},
                status="failure",
            )
            if raise_on_error:
                raise ValidationError(error_message)
            return None

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            deployment_run,
            status=DeploymentStatus.DEPLOYED.value,
            completed_at=completed_at,
            live_url=output.live_url,
            rollback_available=output.rollback_available,
            rollback_metadata=rollback_metadata,
            validation_score=validation.score,
        )

        approval_run = await self.approval_run_repo.get_with_artifact(approval_id)
        if approval_run:
            await self.approval_run_repo.update(
                approval_run,
                approval_status=WorkflowApprovalStatus.DEPLOYED.value,
            )

        await self.audit_repo.log(
            action="deployment_completed",
            resource_type="deployment_run",
            resource_id=deployment_run.id,
            user_id=user_id,
            details={
                "deployment_status": output.deployment_status,
                "live_url": output.live_url,
                "validation_score": validation.score,
            },
        )

        return artifact_payload

    async def rollback(
        self,
        deployment_id: str,
        current_user: User,
        org_context: OrgContext,
        deployment_target: dict | None = None,
        credential_id: str | None = None,
    ) -> DeploymentRunResponse:
        self._ensure_write(current_user, org_context)
        run = await get_deployment_run_for_org(self.session, deployment_id, org_context)

        # Sprint 35A: resolve a stored credential into the transient rollback target.
        if credential_id:
            credential, secret = await self.secret_manager.resolve_secret(
                credential_id,
                user=current_user,
                org_context=org_context,
                deployment_id=run.id,
                reason="deployment rollback",
            )
            deployment_target = {**(deployment_target or {}), **secret}

        if (
            run.deployment_provider == DeploymentProvider.VM.value
            and not (deployment_target and deployment_target.get("private_key"))
        ):
            raise ValidationError(
                "deployment_target with private_key is required to roll back a VM deployment"
            )
        if (
            run.deployment_provider == DeploymentProvider.KUBERNETES.value
            and not (deployment_target and deployment_target.get("kubeconfig"))
        ):
            raise ValidationError(
                "deployment_target with kubeconfig is required to roll back a Kubernetes deployment"
            )

        if run.status != DeploymentStatus.DEPLOYED.value:
            raise ValidationError(
                f"Rollback requires deployment status DEPLOYED (current: {run.status})"
            )
        if not run.rollback_available:
            raise ValidationError("Rollback is not available for this deployment")

        manifest_name = "application"
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            manifest_name = (
                latest.artifact_json.get("deployment_metadata", {}).get("app_name")
                or manifest_name
            )

        await self.audit_repo.log(
            action="deployment_rollback_started",
            resource_type="deployment_run",
            resource_id=run.id,
            user_id=current_user.id,
            details={"deployment_provider": run.deployment_provider},
        )

        await self.run_repo.update(run, status=DeploymentStatus.ROLLBACK_IN_PROGRESS.value)

        try:
            output, logs = await asyncio.to_thread(
                self.deployer.rollback,
                provider=run.deployment_provider or "AZURE",
                app_name=manifest_name,
                rollback_metadata=run.rollback_metadata or {},
                environment=run.environment,
                deployment_target=deployment_target,
            )
        except Exception as exc:
            await self.run_repo.update(
                run,
                status=DeploymentStatus.FAILED.value,
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="deployment_failed",
                resource_type="deployment_run",
                resource_id=run.id,
                user_id=current_user.id,
                details={"error": str(exc), "phase": "rollback"},
                status="failure",
            )
            raise ValidationError(f"Rollback failed: {exc}") from exc

        await self._persist_logs(run.id, logs)

        await self.run_repo.update(
            run,
            status=DeploymentStatus.ROLLED_BACK.value,
            live_url=output.live_url,
            rollback_available=False,
            completed_at=datetime.now(UTC),
        )

        await self.audit_repo.log(
            action="deployment_rollback_completed",
            resource_type="deployment_run",
            resource_id=run.id,
            user_id=current_user.id,
            details={"live_url": output.live_url},
        )

        updated = await self.run_repo.get_with_artifact(run.id)
        return self._to_response(updated)

    async def delete_deployment(
        self,
        deployment_id: str,
        current_user: User,
        org_context: OrgContext,
    ) -> None:
        self._ensure_write(current_user, org_context)
        run = await get_deployment_run_for_org(self.session, deployment_id, org_context)
        await self.run_repo.hard_delete(run)

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> DeploymentRunResponse:
        run = await get_deployment_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> DeploymentArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("DeploymentArtifact", artifact_id)
        return DeploymentArtifactResponse.model_validate(artifact)

    async def list_deployments(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> DeploymentRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return DeploymentRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> DeploymentRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return DeploymentRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )

    async def list_logs(
        self,
        deployment_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 200,
    ) -> DeploymentLogListResponse:
        await get_deployment_run_for_org(self.session, deployment_id, org_context)
        organization_id = org_context.requires_organization
        items, total = await self.log_repo.list_for_org_run(
            deployment_id, organization_id, offset=offset, limit=limit
        )
        return DeploymentLogListResponse(
            items=[DeploymentLogResponse.model_validate(item) for item in items],
            total=total,
        )


async def _run_deployment_background(run_id: str, ctx: dict) -> None:
    """Execute a real deployment off the request thread in its own DB session.

    Uses the existing status machine (PENDING -> QUEUED -> DEPLOYING ->
    DEPLOYED/FAILED). Failures are persisted as a FAILED run; nothing is raised
    back to the (already-returned) HTTP request.
    """
    from app.database.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            service = DeploymentService(session)
            try:
                await service._perform_deployment(
                    run_id=run_id, ctx=ctx, raise_on_error=False
                )
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                logger.error(
                    "deployment_background_unhandled", run_id=run_id, error=str(exc)
                )
                await _mark_run_failed(run_id, str(exc))
    except Exception as exc:  # noqa: BLE001 — never let a background task crash silently
        logger.error("deployment_background_session_failed", run_id=run_id, error=str(exc))


async def _mark_run_failed(run_id: str, error_message: str) -> None:
    from app.database.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            repo = DeploymentRunRepository(session)
            run = await repo.get_with_artifact(run_id)
            if run and run.status not in (
                DeploymentStatus.DEPLOYED.value,
                DeploymentStatus.FAILED.value,
            ):
                await repo.update(
                    run,
                    status=DeploymentStatus.FAILED.value,
                    error_message=error_message,
                    completed_at=datetime.now(UTC),
                )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("deployment_mark_failed_error", run_id=run_id, error=str(exc))
