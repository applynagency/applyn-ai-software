from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.frontend_execution import FrontendExecutionAgent
from app.auth.org_context import OrgContext
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.frontend_execution.executor import FrontendExecutionExecutor
from app.frontend_execution.markdown import output_to_markdown
from app.frontend_execution.validator import FrontendExecutionValidator
from app.models.frontend_code_review import FrontendCodeReviewRunStatus
from app.models.frontend_execution import (
    FrontendExecutionApprovalStatus,
    FrontendExecutionRun,
    FrontendExecutionRunStatus,
)
from app.models.frontend_v3 import FrontendV3RunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.frontend_code_review import FrontendCodeReviewRunRepository
from app.repositories.frontend_execution import (
    FrontendExecutionArtifactRepository,
    FrontendExecutionRunRepository,
)
from app.repositories.frontend_v3 import FrontendV3RunRepository
from app.repositories.project import ProjectRepository
from app.schemas.frontend_execution import (
    FrontendExecutionArtifactResponse,
    FrontendExecutionRunListResponse,
    FrontendExecutionRunRequest,
    FrontendExecutionRunResponse,
)
from app.tenancy.guards import get_frontend_execution_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class FrontendExecutionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = FrontendExecutionRunRepository(session)
        self.artifact_repo = FrontendExecutionArtifactRepository(session)
        self.v3_run_repo = FrontendV3RunRepository(session)
        self.review_run_repo = FrontendCodeReviewRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = FrontendExecutionValidator()
        self.executor = FrontendExecutionExecutor()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: FrontendExecutionRun) -> FrontendExecutionRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = FrontendExecutionArtifactResponse.model_validate(latest)
        return FrontendExecutionRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            frontend_v3_run_id=run.frontend_v3_run_id,
            frontend_code_review_run_id=run.frontend_code_review_run_id,
            status=run.status,
            build_status=run.build_status,
            validation_status=run.validation_status,
            approval_status=run.approval_status,
            created_by=run.created_by,
            created_at=run.created_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            executor_version=run.executor_version,
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

    async def _resolve_frontend_code_review_output(
        self,
        *,
        requirement_id: str,
        frontend_code_review_run_id: str | None,
    ) -> tuple[str, dict]:
        if frontend_code_review_run_id:
            review_run = await self.review_run_repo.get_with_artifact(frontend_code_review_run_id)
            if not review_run or review_run.requirement_id != requirement_id:
                raise NotFoundError("FrontendCodeReviewRun", frontend_code_review_run_id or "")
            if review_run.status != FrontendCodeReviewRunStatus.COMPLETED:
                raise ValidationError("Frontend Code Review run is not completed")
        else:
            items, _ = await self.review_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == FrontendCodeReviewRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Frontend Code Review run found for this requirement. "
                    "Run Frontend Code Review first."
                )
            review_run = completed[0]

        if not review_run.artifacts:
            raise ValidationError("Frontend Code Review run has no output")

        latest_artifact = sorted(
            review_run.artifacts, key=lambda item: item.created_at, reverse=True
        )[0]
        return review_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: FrontendExecutionRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> FrontendExecutionRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        try:
            execution_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                user=current_user,
                frontend_v3_run_id=data.frontend_v3_run_id,
                frontend_code_review_run_id=data.frontend_code_review_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(execution_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        user: User,
        frontend_v3_run_id: str | None = None,
        frontend_code_review_run_id: str | None = None,
    ) -> tuple[FrontendExecutionRun, dict]:
        """Run Frontend Execution agent from workflow dispatcher without API permission checks."""
        v3_run_id, v3_output = await self._resolve_frontend_v3_output(
            requirement_id=requirement_id,
            frontend_v3_run_id=frontend_v3_run_id,
        )
        review_run_id, review_output = await self._resolve_frontend_code_review_output(
            requirement_id=requirement_id,
            frontend_code_review_run_id=frontend_code_review_run_id,
        )

        executor_version = self.executor.get_executor_version()

        execution_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            frontend_v3_run_id=v3_run_id,
            frontend_code_review_run_id=review_run_id,
            status=FrontendExecutionRunStatus.PENDING,
            created_by=user.id,
            executor_version=executor_version,
        )

        await self.audit_repo.log(
            action="frontend_execution_started",
            resource_type="frontend_execution_run",
            resource_id=execution_run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "frontend_v3_run_id": v3_run_id,
                "frontend_code_review_run_id": review_run_id,
            },
        )

        await self.run_repo.update(execution_run, status=FrontendExecutionRunStatus.RUNNING)

        try:
            agent = FrontendExecutionAgent()
            output = await agent.run(
                frontend_v3_output=v3_output,
                frontend_code_review_output=review_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                execution_run,
                status=FrontendExecutionRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="frontend_execution_failed",
                resource_type="frontend_execution_run",
                resource_id=execution_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.run_repo.update(
                execution_run,
                status=FrontendExecutionRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="frontend_execution_failed",
                resource_type="frontend_execution_run",
                resource_id=execution_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Frontend Execution output failed validation (score: {validation.score})"
            )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

        await self.artifact_repo.create(
            run_id=execution_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            build_status=output.build_status,
            validation_status=output.validation_status,
            approval_status=output.approval_status,
            executor_version=executor_version,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            execution_run,
            status=FrontendExecutionRunStatus.COMPLETED,
            completed_at=completed_at,
            build_status=output.build_status,
            validation_status=output.validation_status,
            approval_status=output.approval_status,
        )

        await self.audit_repo.log(
            action="frontend_execution_completed",
            resource_type="frontend_execution_run",
            resource_id=execution_run.id,
            user_id=user.id,
            details={
                "build_status": output.build_status,
                "validation_status": output.validation_status,
                "approval_status": output.approval_status,
            },
        )

        if output.approval_status in (
            FrontendExecutionApprovalStatus.FRONTEND_APPROVED.value,
            FrontendExecutionApprovalStatus.FRONTEND_APPROVED_WITH_WARNINGS.value,
        ):
            await self.audit_repo.log(
                action="frontend_execution_approved",
                resource_type="frontend_execution_run",
                resource_id=execution_run.id,
                user_id=user.id,
                details={"approval_status": output.approval_status},
            )

        return execution_run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> FrontendExecutionRunResponse:
        run = await get_frontend_execution_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> FrontendExecutionArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("FrontendExecutionArtifact", artifact_id)
        return FrontendExecutionArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> FrontendExecutionRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return FrontendExecutionRunListResponse(
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
    ) -> FrontendExecutionRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return FrontendExecutionRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
