from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sre_approval import SreApprovalAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.cicd_agent import CicdRunStatus
from app.models.docker_agent import DockerAgentRunStatus
from app.models.infrastructure_architect import InfrastructureArchitectRunStatus
from app.models.kubernetes_agent import KubernetesRunStatus
from app.models.observability_agent import ObservabilityRunStatus
from app.models.sre_approval import SreApprovalRun, SreApprovalRunStatus, SreStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.cicd_agent import CicdRunRepository
from app.repositories.docker_agent import DockerAgentRunRepository
from app.repositories.infrastructure_architect import InfrastructureArchitectRunRepository
from app.repositories.kubernetes_agent import KubernetesRunRepository
from app.repositories.observability_agent import ObservabilityRunRepository
from app.repositories.project import ProjectRepository
from app.repositories.sre_approval import (
    SreApprovalArtifactRepository,
    SreApprovalRunRepository,
)
from app.schemas.sre_approval import (
    SreApprovalArtifactResponse,
    SreApprovalRunListResponse,
    SreApprovalRunRequest,
    SreApprovalRunResponse,
)
from app.sre_approval.markdown import output_to_markdown
from app.sre_approval.prompt_builder import SreApprovalPromptBuilder
from app.sre_approval.validator import SreApprovalValidator
from app.tenancy.guards import get_requirement_for_org, get_sre_approval_run_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class SreApprovalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = SreApprovalRunRepository(session)
        self.artifact_repo = SreApprovalArtifactRepository(session)
        self.kubernetes_run_repo = KubernetesRunRepository(session)
        self.observability_run_repo = ObservabilityRunRepository(session)
        self.cicd_run_repo = CicdRunRepository(session)
        self.docker_run_repo = DockerAgentRunRepository(session)
        self.infra_run_repo = InfrastructureArchitectRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = SreApprovalValidator()
        self.prompt_builder = SreApprovalPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: SreApprovalRun) -> SreApprovalRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = SreApprovalArtifactResponse.model_validate(latest)
        return SreApprovalRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            kubernetes_run_id=run.kubernetes_run_id,
            observability_run_id=run.observability_run_id,
            status=run.status,
            created_by=run.created_by,
            created_at=run.created_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            tokens_used=run.tokens_used,
            validation_score=run.validation_score,
            prompt_version=run.prompt_version,
            model_used=run.model_used,
            artifact=artifact,
        )

    @staticmethod
    def _latest_artifact_json(run) -> dict:
        latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return latest.artifact_json

    async def _resolve_kubernetes_output(
        self,
        *,
        requirement_id: str,
        kubernetes_run_id: str | None,
    ) -> tuple[str, dict]:
        if kubernetes_run_id:
            run = await self.kubernetes_run_repo.get_with_artifact(kubernetes_run_id)
            if not run or run.requirement_id != requirement_id:
                raise NotFoundError("KubernetesRun", kubernetes_run_id or "")
            if run.status != KubernetesRunStatus.COMPLETED:
                raise ValidationError("Kubernetes run is not completed")
        else:
            items, _ = await self.kubernetes_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                item for item in items if item.status == KubernetesRunStatus.COMPLETED and item.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Kubernetes run found for this requirement. "
                    "Run Kubernetes Agent first."
                )
            run = completed[0]
        if not run.artifacts:
            raise ValidationError("Kubernetes run has no output")
        return run.id, self._latest_artifact_json(run)

    async def _resolve_observability_output(
        self,
        *,
        requirement_id: str,
        observability_run_id: str | None,
    ) -> tuple[str, dict]:
        if observability_run_id:
            run = await self.observability_run_repo.get_with_artifact(observability_run_id)
            if not run or run.requirement_id != requirement_id:
                raise NotFoundError("ObservabilityRun", observability_run_id or "")
            if run.status != ObservabilityRunStatus.COMPLETED:
                raise ValidationError("Observability run is not completed")
        else:
            items, _ = await self.observability_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                item
                for item in items
                if item.status == ObservabilityRunStatus.COMPLETED and item.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Observability run found for this requirement. "
                    "Run Observability Agent first."
                )
            run = completed[0]
        if not run.artifacts:
            raise ValidationError("Observability run has no output")
        return run.id, self._latest_artifact_json(run)

    async def _resolve_completed_output(self, *, repo, completed_status, requirement_id: str, label: str) -> dict:
        items, _ = await repo.list_by_requirement(requirement_id, limit=100)
        completed = [item for item in items if item.status == completed_status and item.artifacts]
        if not completed:
            raise ValidationError(
                f"No completed {label} run found for this requirement. Run {label} first."
            )
        return self._latest_artifact_json(completed[0])

    async def run(
        self,
        data: SreApprovalRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> SreApprovalRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        sre_run, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            kubernetes_run_id=data.kubernetes_run_id,
            observability_run_id=data.observability_run_id,
        )

        run = await self.run_repo.get_with_artifact(sre_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        kubernetes_run_id: str | None = None,
        observability_run_id: str | None = None,
    ) -> tuple[SreApprovalRun, dict]:
        """Run SRE Approval agent from workflow dispatcher without API permission checks."""
        infra_output = await self._resolve_completed_output(
            repo=self.infra_run_repo,
            completed_status=InfrastructureArchitectRunStatus.COMPLETED,
            requirement_id=requirement_id,
            label="Infrastructure Architect",
        )
        docker_output = await self._resolve_completed_output(
            repo=self.docker_run_repo,
            completed_status=DockerAgentRunStatus.COMPLETED,
            requirement_id=requirement_id,
            label="Docker Agent",
        )
        cicd_output = await self._resolve_completed_output(
            repo=self.cicd_run_repo,
            completed_status=CicdRunStatus.COMPLETED,
            requirement_id=requirement_id,
            label="CI/CD Agent",
        )
        kubernetes_run_id_resolved, kubernetes_output = await self._resolve_kubernetes_output(
            requirement_id=requirement_id,
            kubernetes_run_id=kubernetes_run_id,
        )
        observability_run_id_resolved, observability_output = await self._resolve_observability_output(
            requirement_id=requirement_id,
            observability_run_id=observability_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            kubernetes_run_id=kubernetes_run_id_resolved,
            observability_run_id=observability_run_id_resolved,
            status=SreApprovalRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="sre_approval_started",
            resource_type="sre_approval_run",
            resource_id=run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "kubernetes_run_id": kubernetes_run_id_resolved,
                "observability_run_id": observability_run_id_resolved,
            },
        )

        await self.run_repo.update(run, status=SreApprovalRunStatus.RUNNING)

        try:
            agent = SreApprovalAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                infrastructure_architect_output=infra_output,
                docker_agent_output=docker_output,
                cicd_agent_output=cicd_output,
                kubernetes_output=kubernetes_output,
                observability_output=observability_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=SreApprovalRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="sre_approval_failed",
                resource_type="sre_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.run_repo.update(
                run,
                status=SreApprovalRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="sre_approval_failed",
                resource_type="sre_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(
                f"SRE Approval output failed validation (score: {validation.score})"
            )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump(mode="json")

        await self.artifact_repo.create(
            run_id=run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            validation_score=validation.score,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            run,
            status=SreApprovalRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        if output.sre_status == SreStatus.SRE_REJECTED:
            await self.audit_repo.log(
                action="sre_rejected",
                resource_type="sre_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={
                    "sre_status": output.sre_status.value,
                    "production_readiness_score": output.production_readiness_score,
                },
                status="failure",
            )
        else:
            await self.audit_repo.log(
                action="sre_approved",
                resource_type="sre_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={
                    "sre_status": output.sre_status.value,
                    "production_readiness_score": output.production_readiness_score,
                },
            )

        await self.audit_repo.log(
            action="sre_approval_completed",
            resource_type="sre_approval_run",
            resource_id=run.id,
            user_id=user.id,
            details={
                "validation_score": validation.score,
                "tokens_used": tokens_used,
                "sre_status": output.sre_status.value,
                "production_readiness_score": output.production_readiness_score,
            },
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> SreApprovalRunResponse:
        run = await get_sre_approval_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> SreApprovalArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("SreApprovalArtifact", artifact_id)
        return SreApprovalArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> SreApprovalRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return SreApprovalRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
