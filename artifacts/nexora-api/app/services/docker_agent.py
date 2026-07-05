from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.docker_agent import DockerAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.docker_agent.markdown import output_to_markdown
from app.docker_agent.prompt_builder import DockerAgentPromptBuilder
from app.docker_agent.validator import DockerAgentValidator
from app.models.docker_agent import DockerAgentRun, DockerAgentRunStatus
from app.models.infrastructure_architect import InfrastructureArchitectRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.docker_agent import DockerAgentArtifactRepository, DockerAgentRunRepository
from app.repositories.infrastructure_architect import InfrastructureArchitectRunRepository
from app.repositories.project import ProjectRepository
from app.schemas.docker_agent import (
    DockerAgentArtifactResponse,
    DockerAgentRunListResponse,
    DockerAgentRunRequest,
    DockerAgentRunResponse,
)
from app.tenancy.guards import get_docker_agent_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class DockerAgentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = DockerAgentRunRepository(session)
        self.artifact_repo = DockerAgentArtifactRepository(session)
        self.infra_run_repo = InfrastructureArchitectRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = DockerAgentValidator()
        self.prompt_builder = DockerAgentPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: DockerAgentRun) -> DockerAgentRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = DockerAgentArtifactResponse.model_validate(latest)
        return DockerAgentRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            infrastructure_architect_run_id=run.infrastructure_architect_run_id,
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

    async def _resolve_infrastructure_architect_output(
        self,
        *,
        requirement_id: str,
        infrastructure_architect_run_id: str | None,
    ) -> tuple[str, dict]:
        if infrastructure_architect_run_id:
            infra_run = await self.infra_run_repo.get_with_artifact(infrastructure_architect_run_id)
            if not infra_run or infra_run.requirement_id != requirement_id:
                raise NotFoundError(
                    "InfrastructureArchitectRun", infrastructure_architect_run_id or ""
                )
            if infra_run.status != InfrastructureArchitectRunStatus.COMPLETED:
                raise ValidationError("Infrastructure Architect run is not completed")
        else:
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
            infra_run = completed[0]

        if not infra_run.artifacts:
            raise ValidationError("Infrastructure Architect run has no output")

        latest_artifact = sorted(infra_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return infra_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: DockerAgentRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> DockerAgentRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        docker_run, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            infrastructure_architect_run_id=data.infrastructure_architect_run_id,
        )

        run = await self.run_repo.get_with_artifact(docker_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        infrastructure_architect_run_id: str | None = None,
    ) -> tuple[DockerAgentRun, dict]:
        """Run Docker Agent from workflow dispatcher without API permission checks."""
        infra_run_id, infra_output = await self._resolve_infrastructure_architect_output(
            requirement_id=requirement_id,
            infrastructure_architect_run_id=infrastructure_architect_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            infrastructure_architect_run_id=infra_run_id,
            status=DockerAgentRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="docker_agent_started",
            resource_type="docker_agent_run",
            resource_id=run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "infrastructure_architect_run_id": infra_run_id,
            },
        )

        await self.run_repo.update(run, status=DockerAgentRunStatus.RUNNING)

        try:
            agent = DockerAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                infrastructure_architect_output=infra_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=DockerAgentRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="docker_agent_failed",
                resource_type="docker_agent_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="docker_agent_validated",
                resource_type="docker_agent_run",
                resource_id=run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                run,
                status=DockerAgentRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="docker_agent_failed",
                resource_type="docker_agent_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(f"Docker Agent output failed validation (score: {validation.score})")

        await self.audit_repo.log(
            action="docker_agent_validated",
            resource_type="docker_agent_run",
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
            status=DockerAgentRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="docker_agent_completed",
            resource_type="docker_agent_run",
            resource_id=run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> DockerAgentRunResponse:
        run = await get_docker_agent_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> DockerAgentArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("DockerAgentArtifact", artifact_id)
        return DockerAgentArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> DockerAgentRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return DockerAgentRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
