from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.backend_execution import BackendExecutionAgent
from app.auth.org_context import OrgContext
from app.backend_execution.executor import BackendExecutionExecutor
from app.backend_execution.markdown import output_to_markdown
from app.backend_execution.validator import BackendExecutionValidator
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.backend_code_review import BackendCodeReviewRunStatus
from app.models.backend_execution import (
    BackendExecutionApprovalStatus,
    BackendExecutionRun,
    BackendExecutionRunStatus,
)
from app.models.backend_v3 import BackendV3RunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.backend_code_review import BackendCodeReviewRunRepository
from app.repositories.backend_execution import (
    BackendExecutionArtifactRepository,
    BackendExecutionRunRepository,
)
from app.repositories.backend_v3 import BackendV3RunRepository
from app.repositories.project import ProjectRepository
from app.schemas.backend_execution import (
    BackendExecutionArtifactResponse,
    BackendExecutionRunListResponse,
    BackendExecutionRunRequest,
    BackendExecutionRunResponse,
)
from app.tenancy.guards import get_backend_execution_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class BackendExecutionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = BackendExecutionRunRepository(session)
        self.artifact_repo = BackendExecutionArtifactRepository(session)
        self.v3_run_repo = BackendV3RunRepository(session)
        self.review_run_repo = BackendCodeReviewRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = BackendExecutionValidator()
        self.executor = BackendExecutionExecutor()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: BackendExecutionRun) -> BackendExecutionRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = BackendExecutionArtifactResponse.model_validate(latest)
        return BackendExecutionRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            backend_v3_run_id=run.backend_v3_run_id,
            backend_code_review_run_id=run.backend_code_review_run_id,
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

    async def _resolve_backend_code_review_output(
        self,
        *,
        requirement_id: str,
        backend_code_review_run_id: str | None,
    ) -> tuple[str, dict]:
        if backend_code_review_run_id:
            review_run = await self.review_run_repo.get_with_artifact(backend_code_review_run_id)
            if not review_run or review_run.requirement_id != requirement_id:
                raise NotFoundError("BackendCodeReviewRun", backend_code_review_run_id or "")
            if review_run.status != BackendCodeReviewRunStatus.COMPLETED:
                raise ValidationError("Backend Code Review run is not completed")
        else:
            items, _ = await self.review_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == BackendCodeReviewRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Backend Code Review run found for this requirement. "
                    "Run Backend Code Review first."
                )
            review_run = completed[0]

        if not review_run.artifacts:
            raise ValidationError("Backend Code Review run has no output")

        latest_artifact = sorted(
            review_run.artifacts, key=lambda item: item.created_at, reverse=True
        )[0]
        return review_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: BackendExecutionRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> BackendExecutionRunResponse:
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
                backend_v3_run_id=data.backend_v3_run_id,
                backend_code_review_run_id=data.backend_code_review_run_id,
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
        backend_v3_run_id: str | None = None,
        backend_code_review_run_id: str | None = None,
    ) -> tuple[BackendExecutionRun, dict]:
        """Run Backend Execution agent from workflow dispatcher without API permission checks."""
        v3_run_id, v3_output = await self._resolve_backend_v3_output(
            requirement_id=requirement_id,
            backend_v3_run_id=backend_v3_run_id,
        )
        review_run_id, review_output = await self._resolve_backend_code_review_output(
            requirement_id=requirement_id,
            backend_code_review_run_id=backend_code_review_run_id,
        )

        executor_version = self.executor.get_executor_version()

        execution_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            backend_v3_run_id=v3_run_id,
            backend_code_review_run_id=review_run_id,
            status=BackendExecutionRunStatus.PENDING,
            created_by=user.id,
            executor_version=executor_version,
        )

        await self.audit_repo.log(
            action="backend_execution_started",
            resource_type="backend_execution_run",
            resource_id=execution_run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "backend_v3_run_id": v3_run_id,
                "backend_code_review_run_id": review_run_id,
            },
        )

        await self.run_repo.update(execution_run, status=BackendExecutionRunStatus.RUNNING)

        try:
            agent = BackendExecutionAgent()
            output = await agent.run(
                backend_v3_output=v3_output,
                backend_code_review_output=review_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                execution_run,
                status=BackendExecutionRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="backend_execution_failed",
                resource_type="backend_execution_run",
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
                status=BackendExecutionRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="backend_execution_failed",
                resource_type="backend_execution_run",
                resource_id=execution_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Backend Execution output failed validation (score: {validation.score})"
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
            status=BackendExecutionRunStatus.COMPLETED,
            completed_at=completed_at,
            build_status=output.build_status,
            validation_status=output.validation_status,
            approval_status=output.approval_status,
        )

        await self.audit_repo.log(
            action="backend_execution_completed",
            resource_type="backend_execution_run",
            resource_id=execution_run.id,
            user_id=user.id,
            details={
                "build_status": output.build_status,
                "validation_status": output.validation_status,
                "approval_status": output.approval_status,
            },
        )

        if output.approval_status in (
            BackendExecutionApprovalStatus.BACKEND_APPROVED.value,
            BackendExecutionApprovalStatus.BACKEND_APPROVED_WITH_WARNINGS.value,
        ):
            await self.audit_repo.log(
                action="backend_execution_approved",
                resource_type="backend_execution_run",
                resource_id=execution_run.id,
                user_id=user.id,
                details={"approval_status": output.approval_status},
            )

        return execution_run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> BackendExecutionRunResponse:
        run = await get_backend_execution_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> BackendExecutionArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("BackendExecutionArtifact", artifact_id)
        return BackendExecutionArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> BackendExecutionRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return BackendExecutionRunListResponse(
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
    ) -> BackendExecutionRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return BackendExecutionRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
