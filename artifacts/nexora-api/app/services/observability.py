from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.observability_agent import ObservabilityAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.kubernetes_agent import KubernetesRunStatus
from app.models.observability_agent import ObservabilityRun, ObservabilityRunStatus
from app.models.user import User
from app.observability_agent.markdown import output_to_markdown
from app.observability_agent.prompt_builder import ObservabilityAgentPromptBuilder
from app.observability_agent.validator import ObservabilityAgentValidator
from app.repositories.audit import AuditLogRepository
from app.repositories.kubernetes_agent import KubernetesRunRepository
from app.repositories.observability_agent import (
    ObservabilityArtifactRepository,
    ObservabilityRunRepository,
)
from app.repositories.project import ProjectRepository
from app.schemas.observability_agent import (
    ObservabilityArtifactResponse,
    ObservabilityRunListResponse,
    ObservabilityRunRequest,
    ObservabilityRunResponse,
)
from app.tenancy.guards import get_observability_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class ObservabilityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = ObservabilityRunRepository(session)
        self.artifact_repo = ObservabilityArtifactRepository(session)
        self.kubernetes_run_repo = KubernetesRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = ObservabilityAgentValidator()
        self.prompt_builder = ObservabilityAgentPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: ObservabilityRun) -> ObservabilityRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = ObservabilityArtifactResponse.model_validate(latest)
        return ObservabilityRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            kubernetes_run_id=run.kubernetes_run_id,
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

    async def _resolve_kubernetes_output(
        self,
        *,
        requirement_id: str,
        kubernetes_run_id: str | None,
    ) -> tuple[str, dict]:
        if kubernetes_run_id:
            k8s_run = await self.kubernetes_run_repo.get_with_artifact(kubernetes_run_id)
            if not k8s_run or k8s_run.requirement_id != requirement_id:
                raise NotFoundError("KubernetesRun", kubernetes_run_id or "")
            if k8s_run.status != KubernetesRunStatus.COMPLETED:
                raise ValidationError("Kubernetes run is not completed")
        else:
            items, _ = await self.kubernetes_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run for run in items if run.status == KubernetesRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Kubernetes run found for this requirement. "
                    "Run Kubernetes Agent first."
                )
            k8s_run = completed[0]

        if not k8s_run.artifacts:
            raise ValidationError("Kubernetes run has no output")

        latest = sorted(k8s_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return k8s_run.id, latest.artifact_json

    async def run(
        self,
        data: ObservabilityRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> ObservabilityRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        obs_run, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            kubernetes_run_id=data.kubernetes_run_id,
        )

        run = await self.run_repo.get_with_artifact(obs_run.id)
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
    ) -> tuple[ObservabilityRun, dict]:
        """Run Observability Agent from workflow dispatcher without API permission checks."""
        kubernetes_run_id_resolved, kubernetes_output = await self._resolve_kubernetes_output(
            requirement_id=requirement_id,
            kubernetes_run_id=kubernetes_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            kubernetes_run_id=kubernetes_run_id_resolved,
            status=ObservabilityRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="observability_started",
            resource_type="observability_run",
            resource_id=run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "kubernetes_run_id": kubernetes_run_id_resolved,
            },
        )

        await self.run_repo.update(run, status=ObservabilityRunStatus.RUNNING)

        try:
            agent = ObservabilityAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                kubernetes_output=kubernetes_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=ObservabilityRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="observability_failed",
                resource_type="observability_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="observability_validated",
                resource_type="observability_run",
                resource_id=run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                run,
                status=ObservabilityRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="observability_failed",
                resource_type="observability_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(
                f"Observability output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="observability_validated",
            resource_type="observability_run",
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
            status=ObservabilityRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="observability_completed",
            resource_type="observability_run",
            resource_id=run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> ObservabilityRunResponse:
        run = await get_observability_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> ObservabilityArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("ObservabilityArtifact", artifact_id)
        return ObservabilityArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> ObservabilityRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return ObservabilityRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
