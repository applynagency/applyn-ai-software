from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.uiux_designer import UIUXDesignerAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.business_analyst import BusinessAnalystRunStatus
from app.models.uiux_designer import UIUXRun, UIUXRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.business_analyst import BusinessAnalystRunRepository
from app.repositories.project import ProjectRepository
from app.repositories.uiux_designer import UIUXArtifactRepository, UIUXRunRepository
from app.schemas.uiux_designer import (
    UIUXArtifactResponse,
    UIUXRunListResponse,
    UIUXRunRequest,
    UIUXRunResponse,
)
from app.tenancy.guards import get_requirement_for_org, get_uiux_run_for_org
from app.tenancy.permissions import can_write_resources
from app.uiux_designer.markdown import output_to_markdown
from app.uiux_designer.prompt_builder import UIUXPromptBuilder
from app.uiux_designer.validator import UIUXValidator

logger = get_logger(__name__)


class UIUXDesignerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = UIUXRunRepository(session)
        self.artifact_repo = UIUXArtifactRepository(session)
        self.ba_run_repo = BusinessAnalystRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = UIUXValidator()
        self.prompt_builder = UIUXPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: UIUXRun) -> UIUXRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = UIUXArtifactResponse.model_validate(latest)
        return UIUXRunResponse(
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
        data: UIUXRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> UIUXRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        try:
            uiux_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                business_analyst_run_id=data.business_analyst_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(uiux_run.id)
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
    ) -> tuple[UIUXRun, dict]:
        """Run UI/UX Designer agent from workflow dispatcher without API permission checks."""
        ba_run_id, ba_output = await self._resolve_business_analyst_output(
            requirement_id=requirement_id,
            business_analyst_run_id=business_analyst_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        uiux_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            business_analyst_run_id=ba_run_id,
            status=UIUXRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="uiux_started",
            resource_type="uiux_run",
            resource_id=uiux_run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "business_analyst_run_id": ba_run_id},
        )

        await self.run_repo.update(uiux_run, status=UIUXRunStatus.RUNNING)

        try:
            agent = UIUXDesignerAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                business_analyst_output=ba_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                uiux_run,
                status=UIUXRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="uiux_failed",
                resource_type="uiux_run",
                resource_id=uiux_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="uiux_validated",
                resource_type="uiux_run",
                resource_id=uiux_run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                uiux_run,
                status=UIUXRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="uiux_failed",
                resource_type="uiux_run",
                resource_id=uiux_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"UI/UX Designer output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="uiux_validated",
            resource_type="uiux_run",
            resource_id=uiux_run.id,
            user_id=user.id,
            details={"score": validation.score, "counts": validation.counts},
        )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

        await self.artifact_repo.create(
            run_id=uiux_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            validation_score=validation.score,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            uiux_run,
            status=UIUXRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="uiux_completed",
            resource_type="uiux_run",
            resource_id=uiux_run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return uiux_run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> UIUXRunResponse:
        run = await get_uiux_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> UIUXArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("UIUXArtifact", artifact_id)
        return UIUXArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> UIUXRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return UIUXRunListResponse(
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
    ) -> UIUXRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return UIUXRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
