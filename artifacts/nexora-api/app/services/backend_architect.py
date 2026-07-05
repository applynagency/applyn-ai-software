from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.backend_architect import BackendArchitectAgent
from app.auth.org_context import OrgContext
from app.backend_architect.markdown import output_to_markdown
from app.backend_architect.prompt_builder import BackendArchitectPromptBuilder
from app.backend_architect.validator import BackendArchitectValidator
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.backend_architect import BackendArchitectRun, BackendArchitectRunStatus
from app.models.business_analyst import BusinessAnalystRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.backend_architect import (
    BackendArchitectArtifactRepository,
    BackendArchitectRunRepository,
)
from app.repositories.business_analyst import BusinessAnalystRunRepository
from app.repositories.project import ProjectRepository
from app.schemas.backend_architect import (
    BackendArchitectArtifactResponse,
    BackendArchitectRunListResponse,
    BackendArchitectRunRequest,
    BackendArchitectRunResponse,
)
from app.tenancy.guards import get_backend_architect_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class BackendArchitectService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = BackendArchitectRunRepository(session)
        self.artifact_repo = BackendArchitectArtifactRepository(session)
        self.ba_run_repo = BusinessAnalystRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = BackendArchitectValidator()
        self.prompt_builder = BackendArchitectPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: BackendArchitectRun) -> BackendArchitectRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = BackendArchitectArtifactResponse.model_validate(latest)
        return BackendArchitectRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            business_analyst_run_id=run.business_analyst_run_id,
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

    async def _resolve_business_analyst_output(
        self,
        *,
        requirement_id: str,
        business_analyst_run_id: str | None,
    ) -> tuple[str, dict]:
        if business_analyst_run_id:
            ba_run = await self.ba_run_repo.get_with_artifact(business_analyst_run_id)
            if not ba_run or ba_run.requirement_id != requirement_id:
                raise NotFoundError("BusinessAnalystRun", business_analyst_run_id or "")
            if ba_run.status != BusinessAnalystRunStatus.COMPLETED:
                raise ValidationError("Business Analyst run is not completed")
        else:
            items, _ = await self.ba_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == BusinessAnalystRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Business Analyst run found for this requirement. Run Business Analyst first."
                )
            ba_run = completed[0]

        if not ba_run.artifacts:
            raise ValidationError("Business Analyst run has no output")

        latest_artifact = sorted(ba_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return ba_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: BackendArchitectRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> BackendArchitectRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        try:
            architect_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                business_analyst_run_id=data.business_analyst_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(architect_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        business_analyst_run_id: str | None = None,
    ) -> tuple[BackendArchitectRun, dict]:
        """Run Backend Architect agent from workflow dispatcher without API permission checks."""
        ba_run_id, ba_output = await self._resolve_business_analyst_output(
            requirement_id=requirement_id,
            business_analyst_run_id=business_analyst_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            business_analyst_run_id=ba_run_id,
            status=BackendArchitectRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="backend_architect_started",
            resource_type="backend_architect_run",
            resource_id=run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "business_analyst_run_id": ba_run_id},
        )

        await self.run_repo.update(run, status=BackendArchitectRunStatus.RUNNING)

        try:
            agent = BackendArchitectAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                business_analyst_output=ba_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=BackendArchitectRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="backend_architect_failed",
                resource_type="backend_architect_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="backend_architect_validated",
                resource_type="backend_architect_run",
                resource_id=run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                run,
                status=BackendArchitectRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="backend_architect_failed",
                resource_type="backend_architect_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(
                f"Backend Architect output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="backend_architect_validated",
            resource_type="backend_architect_run",
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
            status=BackendArchitectRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="backend_architect_completed",
            resource_type="backend_architect_run",
            resource_id=run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> BackendArchitectRunResponse:
        run = await get_backend_architect_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> BackendArchitectArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("BackendArchitectArtifact", artifact_id)
        return BackendArchitectArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> BackendArchitectRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return BackendArchitectRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )

    async def list_for_organization(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> BackendArchitectRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return BackendArchitectRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
