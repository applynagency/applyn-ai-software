from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.kubernetes_agent import KubernetesAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.kubernetes_agent.markdown import output_to_markdown
from app.kubernetes_agent.prompt_builder import KubernetesAgentPromptBuilder
from app.kubernetes_agent.validator import KubernetesAgentValidator
from app.models.cicd_agent import CicdRunStatus
from app.models.docker_agent import DockerAgentRunStatus
from app.models.infrastructure_architect import InfrastructureArchitectRunStatus
from app.models.kubernetes_agent import KubernetesRun, KubernetesRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.cicd_agent import CicdRunRepository
from app.repositories.docker_agent import DockerAgentRunRepository
from app.repositories.infrastructure_architect import InfrastructureArchitectRunRepository
from app.repositories.kubernetes_agent import (
    KubernetesArtifactRepository,
    KubernetesRunRepository,
)
from app.repositories.project import ProjectRepository
from app.schemas.kubernetes_agent import (
    KubernetesArtifactResponse,
    KubernetesRunListResponse,
    KubernetesRunRequest,
    KubernetesRunResponse,
)
from app.tenancy.guards import get_kubernetes_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class KubernetesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = KubernetesRunRepository(session)
        self.artifact_repo = KubernetesArtifactRepository(session)
        self.cicd_run_repo = CicdRunRepository(session)
        self.docker_run_repo = DockerAgentRunRepository(session)
        self.infra_run_repo = InfrastructureArchitectRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = KubernetesAgentValidator()
        self.prompt_builder = KubernetesAgentPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: KubernetesRun) -> KubernetesRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = KubernetesArtifactResponse.model_validate(latest)
        return KubernetesRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            cicd_run_id=run.cicd_run_id,
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

    async def _resolve_cicd_output(
        self,
        *,
        requirement_id: str,
        cicd_run_id: str | None,
    ) -> tuple[str, dict]:
        if cicd_run_id:
            cicd_run = await self.cicd_run_repo.get_with_artifact(cicd_run_id)
            if not cicd_run or cicd_run.requirement_id != requirement_id:
                raise NotFoundError("CicdRun", cicd_run_id or "")
            if cicd_run.status != CicdRunStatus.COMPLETED:
                raise ValidationError("CI/CD Agent run is not completed")
        else:
            items, _ = await self.cicd_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run for run in items if run.status == CicdRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed CI/CD Agent run found for this requirement. "
                    "Run CI/CD Agent first."
                )
            cicd_run = completed[0]

        if not cicd_run.artifacts:
            raise ValidationError("CI/CD Agent run has no output")

        latest = sorted(cicd_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return cicd_run.id, latest.artifact_json

    async def _resolve_docker_output(self, *, requirement_id: str) -> dict:
        items, _ = await self.docker_run_repo.list_by_requirement(requirement_id, limit=100)
        completed = [
            run for run in items if run.status == DockerAgentRunStatus.COMPLETED and run.artifacts
        ]
        if not completed:
            raise ValidationError(
                "No completed Docker Agent run found for this requirement. Run Docker Agent first."
            )
        latest = sorted(completed[0].artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return latest.artifact_json

    async def _resolve_infrastructure_output(self, *, requirement_id: str) -> dict:
        items, _ = await self.infra_run_repo.list_by_requirement(requirement_id, limit=100)
        completed = [
            run
            for run in items
            if run.status == InfrastructureArchitectRunStatus.COMPLETED and run.artifacts
        ]
        if not completed:
            raise ValidationError(
                "No completed Infrastructure Architect run found for this requirement. "
                "Run Infrastructure Architect first."
            )
        latest = sorted(completed[0].artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return latest.artifact_json

    async def run(
        self,
        data: KubernetesRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> KubernetesRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        k8s_run, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            cicd_run_id=data.cicd_run_id,
        )

        run = await self.run_repo.get_with_artifact(k8s_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        cicd_run_id: str | None = None,
    ) -> tuple[KubernetesRun, dict]:
        """Run Kubernetes Agent from workflow dispatcher without API permission checks."""
        infra_output = await self._resolve_infrastructure_output(requirement_id=requirement_id)
        docker_output = await self._resolve_docker_output(requirement_id=requirement_id)
        cicd_run_id_resolved, cicd_output = await self._resolve_cicd_output(
            requirement_id=requirement_id,
            cicd_run_id=cicd_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            cicd_run_id=cicd_run_id_resolved,
            status=KubernetesRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="kubernetes_started",
            resource_type="kubernetes_run",
            resource_id=run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "cicd_run_id": cicd_run_id_resolved},
        )

        await self.run_repo.update(run, status=KubernetesRunStatus.RUNNING)

        try:
            agent = KubernetesAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                infrastructure_architect_output=infra_output,
                docker_agent_output=docker_output,
                cicd_agent_output=cicd_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=KubernetesRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="kubernetes_failed",
                resource_type="kubernetes_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="kubernetes_validated",
                resource_type="kubernetes_run",
                resource_id=run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                run,
                status=KubernetesRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="kubernetes_failed",
                resource_type="kubernetes_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(
                f"Kubernetes output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="kubernetes_validated",
            resource_type="kubernetes_run",
            resource_id=run.id,
            user_id=user.id,
            details={"score": validation.score, "counts": validation.counts},
        )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

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
            status=KubernetesRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="kubernetes_completed",
            resource_type="kubernetes_run",
            resource_id=run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> KubernetesRunResponse:
        run = await get_kubernetes_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> KubernetesArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("KubernetesArtifact", artifact_id)
        return KubernetesArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> KubernetesRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return KubernetesRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
