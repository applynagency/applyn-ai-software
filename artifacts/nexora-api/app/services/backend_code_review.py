from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.backend_code_review import BackendCodeReviewAgent
from app.auth.org_context import OrgContext
from app.backend_code_review.markdown import output_to_markdown
from app.backend_code_review.prompt_builder import BackendCodeReviewPromptBuilder
from app.backend_code_review.validator import BackendCodeReviewValidator
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.backend_code_review import BackendCodeReviewRun, BackendCodeReviewRunStatus
from app.models.backend_v3 import BackendV3RunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.backend_code_review import (
    BackendCodeReviewArtifactRepository,
    BackendCodeReviewRunRepository,
)
from app.repositories.backend_v3 import BackendV3RunRepository
from app.repositories.project import ProjectRepository
from app.schemas.backend_code_review import (
    BackendCodeReviewArtifactResponse,
    BackendCodeReviewRunListResponse,
    BackendCodeReviewRunRequest,
    BackendCodeReviewRunResponse,
)
from app.tenancy.guards import get_backend_code_review_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class BackendCodeReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = BackendCodeReviewRunRepository(session)
        self.artifact_repo = BackendCodeReviewArtifactRepository(session)
        self.v3_run_repo = BackendV3RunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = BackendCodeReviewValidator()
        self.prompt_builder = BackendCodeReviewPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: BackendCodeReviewRun) -> BackendCodeReviewRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = BackendCodeReviewArtifactResponse.model_validate(latest)
        return BackendCodeReviewRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            backend_v3_run_id=run.backend_v3_run_id,
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

    async def _resolve_backend_v3_output(
        self,
        *,
        requirement_id: str,
        backend_v3_run_id: str | None,
    ) -> tuple[str, dict]:
        if backend_v3_run_id:
            v3_run = await self.v3_run_repo.get_with_artifact(backend_v3_run_id)
            if not v3_run or v3_run.requirement_id != requirement_id:
                raise NotFoundError("BackendV3Run", backend_v3_run_id or "")
            if v3_run.status != BackendV3RunStatus.COMPLETED:
                raise ValidationError("Backend Developer V3 run is not completed")
        else:
            items, _ = await self.v3_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == BackendV3RunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Backend Developer V3 run found for this requirement. "
                    "Run Backend Developer V3 first."
                )
            v3_run = completed[0]

        if not v3_run.artifacts:
            raise ValidationError("Backend Developer V3 run has no output")

        latest_artifact = sorted(v3_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return v3_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: BackendCodeReviewRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> BackendCodeReviewRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        review_run, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            backend_v3_run_id=data.backend_v3_run_id,
        )

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
        backend_v3_run_id: str | None = None,
    ) -> tuple[BackendCodeReviewRun, dict]:
        """Run Backend Code Review agent from workflow dispatcher without API permission checks."""
        v3_run_id, v3_output = await self._resolve_backend_v3_output(
            requirement_id=requirement_id,
            backend_v3_run_id=backend_v3_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        review_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            backend_v3_run_id=v3_run_id,
            status=BackendCodeReviewRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="backend_code_review_started",
            resource_type="backend_code_review_run",
            resource_id=review_run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "backend_v3_run_id": v3_run_id},
        )

        await self.run_repo.update(review_run, status=BackendCodeReviewRunStatus.RUNNING)

        try:
            agent = BackendCodeReviewAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                backend_v3_output=v3_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                review_run,
                status=BackendCodeReviewRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="backend_code_review_failed",
                resource_type="backend_code_review_run",
                resource_id=review_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="backend_code_review_validated",
                resource_type="backend_code_review_run",
                resource_id=review_run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                review_run,
                status=BackendCodeReviewRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="backend_code_review_failed",
                resource_type="backend_code_review_run",
                resource_id=review_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Backend Code Review output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="backend_code_review_validated",
            resource_type="backend_code_review_run",
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
            status=BackendCodeReviewRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            review_score=output.review_score,
            approval_status=output.approval_status.value,
        )

        await self.audit_repo.log(
            action="backend_code_review_completed",
            resource_type="backend_code_review_run",
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
    ) -> BackendCodeReviewRunResponse:
        run = await get_backend_code_review_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> BackendCodeReviewArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("BackendCodeReviewArtifact", artifact_id)
        return BackendCodeReviewArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> BackendCodeReviewRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return BackendCodeReviewRunListResponse(
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
    ) -> BackendCodeReviewRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return BackendCodeReviewRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
