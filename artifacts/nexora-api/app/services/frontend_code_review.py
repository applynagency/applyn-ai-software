from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.frontend_code_review import FrontendCodeReviewAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.frontend_code_review.markdown import output_to_markdown
from app.frontend_code_review.prompt_builder import FrontendCodeReviewPromptBuilder
from app.frontend_code_review.validator import FrontendCodeReviewValidator
from app.models.frontend_code_review import FrontendCodeReviewRun, FrontendCodeReviewRunStatus
from app.models.frontend_v3 import FrontendV3RunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.frontend_code_review import (
    FrontendCodeReviewArtifactRepository,
    FrontendCodeReviewRunRepository,
)
from app.repositories.frontend_v3 import FrontendV3RunRepository
from app.repositories.project import ProjectRepository
from app.schemas.frontend_code_review import (
    FrontendCodeReviewArtifactResponse,
    FrontendCodeReviewRunListResponse,
    FrontendCodeReviewRunRequest,
    FrontendCodeReviewRunResponse,
)
from app.tenancy.guards import get_frontend_code_review_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class FrontendCodeReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = FrontendCodeReviewRunRepository(session)
        self.artifact_repo = FrontendCodeReviewArtifactRepository(session)
        self.v3_run_repo = FrontendV3RunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = FrontendCodeReviewValidator()
        self.prompt_builder = FrontendCodeReviewPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: FrontendCodeReviewRun) -> FrontendCodeReviewRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = FrontendCodeReviewArtifactResponse.model_validate(latest)
        return FrontendCodeReviewRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            frontend_v3_run_id=run.frontend_v3_run_id,
            status=run.status,
            approval_status=run.approval_status,
            created_by=run.created_by,
            created_at=run.created_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            tokens_used=run.tokens_used,
            review_score=run.review_score,
            prompt_version=run.prompt_version,
            model_used=run.model_used,
            artifact=artifact,
        )

    async def _resolve_frontend_v3_output(
        self,
        *,
        requirement_id: str,
        frontend_v3_run_id: str | None,
    ) -> tuple[str, dict]:
        if frontend_v3_run_id:
            v3_run = await self.v3_run_repo.get_with_artifact(frontend_v3_run_id)
            if not v3_run or v3_run.requirement_id != requirement_id:
                raise NotFoundError("FrontendV3Run", frontend_v3_run_id or "")
            if v3_run.status != FrontendV3RunStatus.COMPLETED:
                raise ValidationError("Frontend Developer V3 run is not completed")
        else:
            items, _ = await self.v3_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == FrontendV3RunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Frontend Developer V3 run found for this requirement. "
                    "Run Frontend Developer V3 first."
                )
            v3_run = completed[0]

        if not v3_run.artifacts:
            raise ValidationError("Frontend Developer V3 run has no output")

        latest_artifact = sorted(v3_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return v3_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: FrontendCodeReviewRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> FrontendCodeReviewRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        try:
            review_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                frontend_v3_run_id=data.frontend_v3_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(review_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        frontend_v3_run_id: str | None = None,
    ) -> tuple[FrontendCodeReviewRun, dict]:
        """Run Frontend Code Review agent from workflow dispatcher without API permission checks."""
        v3_run_id, v3_output = await self._resolve_frontend_v3_output(
            requirement_id=requirement_id,
            frontend_v3_run_id=frontend_v3_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        review_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            frontend_v3_run_id=v3_run_id,
            status=FrontendCodeReviewRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="frontend_code_review_started",
            resource_type="frontend_code_review_run",
            resource_id=review_run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "frontend_v3_run_id": v3_run_id},
        )

        await self.run_repo.update(review_run, status=FrontendCodeReviewRunStatus.RUNNING)

        try:
            agent = FrontendCodeReviewAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                frontend_v3_output=v3_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                review_run,
                status=FrontendCodeReviewRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="frontend_code_review_failed",
                resource_type="frontend_code_review_run",
                resource_id=review_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="frontend_code_review_validated",
                resource_type="frontend_code_review_run",
                resource_id=review_run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                review_run,
                status=FrontendCodeReviewRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="frontend_code_review_failed",
                resource_type="frontend_code_review_run",
                resource_id=review_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Frontend Code Review output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="frontend_code_review_validated",
            resource_type="frontend_code_review_run",
            resource_id=review_run.id,
            user_id=user.id,
            details={"score": validation.score, "counts": validation.counts},
        )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump(mode="json")

        await self.artifact_repo.create(
            run_id=review_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            review_score=output.review_score,
            approval_status=output.approval_status.value,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            review_run,
            status=FrontendCodeReviewRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            review_score=output.review_score,
            approval_status=output.approval_status.value,
        )

        await self.audit_repo.log(
            action="frontend_code_review_completed",
            resource_type="frontend_code_review_run",
            resource_id=review_run.id,
            user_id=user.id,
            details={
                "review_score": output.review_score,
                "approval_status": output.approval_status.value,
                "tokens_used": tokens_used,
            },
        )

        return review_run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> FrontendCodeReviewRunResponse:
        run = await get_frontend_code_review_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> FrontendCodeReviewArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("FrontendCodeReviewArtifact", artifact_id)
        return FrontendCodeReviewArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> FrontendCodeReviewRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return FrontendCodeReviewRunListResponse(
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
    ) -> FrontendCodeReviewRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return FrontendCodeReviewRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
