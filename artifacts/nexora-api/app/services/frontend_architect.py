from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.frontend_architect import FrontendArchitectAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.frontend_architect.markdown import output_to_markdown
from app.frontend_architect.prompt_builder import FrontendArchitectPromptBuilder
from app.frontend_architect.validator import FrontendArchitectValidator
from app.models.frontend_architect import FrontendArchitectRun, FrontendArchitectRunStatus
from app.models.uiux_designer import UIUXRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.frontend_architect import (
    FrontendArchitectArtifactRepository,
    FrontendArchitectRunRepository,
)
from app.repositories.project import ProjectRepository
from app.repositories.uiux_designer import UIUXRunRepository
from app.schemas.frontend_architect import (
    FrontendArchitectArtifactResponse,
    FrontendArchitectRunListResponse,
    FrontendArchitectRunRequest,
    FrontendArchitectRunResponse,
)
from app.tenancy.guards import get_frontend_architect_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class FrontendArchitectService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = FrontendArchitectRunRepository(session)
        self.artifact_repo = FrontendArchitectArtifactRepository(session)
        self.uiux_run_repo = UIUXRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = FrontendArchitectValidator()
        self.prompt_builder = FrontendArchitectPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: FrontendArchitectRun) -> FrontendArchitectRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = FrontendArchitectArtifactResponse.model_validate(latest)
        return FrontendArchitectRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            uiux_run_id=run.uiux_run_id,
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

    async def _resolve_uiux_output(
        self,
        *,
        requirement_id: str,
        uiux_run_id: str | None,
    ) -> tuple[str, dict]:
        if uiux_run_id:
            uiux_run = await self.uiux_run_repo.get_with_artifact(uiux_run_id)
            if not uiux_run or uiux_run.requirement_id != requirement_id:
                raise NotFoundError("UIUXRun", uiux_run_id or "")
            if uiux_run.status != UIUXRunStatus.COMPLETED:
                raise ValidationError("UI/UX Designer run is not completed")
        else:
            items, _ = await self.uiux_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == UIUXRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed UI/UX Designer run found for this requirement. Run UI/UX Designer first."
                )
            uiux_run = completed[0]

        if not uiux_run.artifacts:
            raise ValidationError("UI/UX Designer run has no output")

        latest_artifact = sorted(uiux_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return uiux_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: FrontendArchitectRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> FrontendArchitectRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        try:
            fa_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                uiux_run_id=data.uiux_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(fa_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        uiux_run_id: str | None = None,
    ) -> tuple[FrontendArchitectRun, dict]:
        """Run Frontend Architect agent from workflow dispatcher without API permission checks."""
        resolved_uiux_run_id, uiux_output = await self._resolve_uiux_output(
            requirement_id=requirement_id,
            uiux_run_id=uiux_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        fa_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            uiux_run_id=resolved_uiux_run_id,
            status=FrontendArchitectRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="frontend_architect_started",
            resource_type="frontend_architect_run",
            resource_id=fa_run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "uiux_run_id": resolved_uiux_run_id},
        )

        await self.run_repo.update(fa_run, status=FrontendArchitectRunStatus.RUNNING)

        try:
            agent = FrontendArchitectAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                uiux_output=uiux_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                fa_run,
                status=FrontendArchitectRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="frontend_architect_failed",
                resource_type="frontend_architect_run",
                resource_id=fa_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="frontend_architect_validated",
                resource_type="frontend_architect_run",
                resource_id=fa_run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                fa_run,
                status=FrontendArchitectRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="frontend_architect_failed",
                resource_type="frontend_architect_run",
                resource_id=fa_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Frontend Architect output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="frontend_architect_validated",
            resource_type="frontend_architect_run",
            resource_id=fa_run.id,
            user_id=user.id,
            details={"score": validation.score, "counts": validation.counts},
        )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

        await self.artifact_repo.create(
            run_id=fa_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            validation_score=validation.score,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            fa_run,
            status=FrontendArchitectRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="frontend_architect_completed",
            resource_type="frontend_architect_run",
            resource_id=fa_run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return fa_run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> FrontendArchitectRunResponse:
        run = await get_frontend_architect_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> FrontendArchitectArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("FrontendArchitectArtifact", artifact_id)
        return FrontendArchitectArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> FrontendArchitectRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return FrontendArchitectRunListResponse(
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
    ) -> FrontendArchitectRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return FrontendArchitectRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
