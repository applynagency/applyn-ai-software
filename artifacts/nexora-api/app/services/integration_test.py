from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.integration_test import IntegrationTestAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.integration_test.markdown import output_to_markdown
from app.integration_test.prompt_builder import IntegrationTestPromptBuilder
from app.integration_test.validator import IntegrationTestValidator
from app.models.backend_execution import BackendExecutionRunStatus
from app.models.frontend_execution import FrontendExecutionRunStatus
from app.models.integration_test import IntegrationTestRun, IntegrationTestRunStatus
from app.models.unit_test import UnitTestRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.backend_execution import BackendExecutionRunRepository
from app.repositories.frontend_execution import FrontendExecutionRunRepository
from app.repositories.integration_test import (
    IntegrationTestArtifactRepository,
    IntegrationTestRunRepository,
)
from app.repositories.project import ProjectRepository
from app.repositories.unit_test import UnitTestRunRepository
from app.schemas.integration_test import (
    IntegrationTestArtifactResponse,
    IntegrationTestRunListResponse,
    IntegrationTestRunRequest,
    IntegrationTestRunResponse,
)
from app.tenancy.guards import get_integration_test_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class IntegrationTestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = IntegrationTestRunRepository(session)
        self.artifact_repo = IntegrationTestArtifactRepository(session)
        self.fe_run_repo = FrontendExecutionRunRepository(session)
        self.be_run_repo = BackendExecutionRunRepository(session)
        self.unit_test_repo = UnitTestRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = IntegrationTestValidator()
        self.prompt_builder = IntegrationTestPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: IntegrationTestRun) -> IntegrationTestRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = IntegrationTestArtifactResponse.model_validate(latest)
        return IntegrationTestRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            frontend_execution_run_id=run.frontend_execution_run_id,
            backend_execution_run_id=run.backend_execution_run_id,
            unit_test_run_id=run.unit_test_run_id,
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

    async def _resolve_frontend_execution_output(
        self,
        *,
        requirement_id: str,
        frontend_execution_run_id: str | None,
    ) -> tuple[str, dict]:
        if frontend_execution_run_id:
            fe_run = await self.fe_run_repo.get_with_artifact(frontend_execution_run_id)
            if not fe_run or fe_run.requirement_id != requirement_id:
                raise NotFoundError("FrontendExecutionRun", frontend_execution_run_id or "")
            if fe_run.status != FrontendExecutionRunStatus.COMPLETED:
                raise ValidationError("Frontend Execution run is not completed")
        else:
            items, _ = await self.fe_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == FrontendExecutionRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Frontend Execution run found for this requirement. "
                    "Run Frontend Execution first."
                )
            fe_run = completed[0]

        if not fe_run.artifacts:
            raise ValidationError("Frontend Execution run has no output")

        latest_artifact = sorted(fe_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return fe_run.id, latest_artifact.artifact_json

    async def _resolve_backend_execution_output(
        self,
        *,
        requirement_id: str,
        backend_execution_run_id: str | None,
    ) -> tuple[str, dict]:
        if backend_execution_run_id:
            be_run = await self.be_run_repo.get_with_artifact(backend_execution_run_id)
            if not be_run or be_run.requirement_id != requirement_id:
                raise NotFoundError("BackendExecutionRun", backend_execution_run_id or "")
            if be_run.status != BackendExecutionRunStatus.COMPLETED:
                raise ValidationError("Backend Execution run is not completed")
        else:
            items, _ = await self.be_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == BackendExecutionRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Backend Execution run found for this requirement. "
                    "Run Backend Execution first."
                )
            be_run = completed[0]

        if not be_run.artifacts:
            raise ValidationError("Backend Execution run has no output")

        latest_artifact = sorted(be_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return be_run.id, latest_artifact.artifact_json

    async def _resolve_unit_test_output(
        self,
        *,
        requirement_id: str,
        unit_test_run_id: str | None,
    ) -> tuple[str, dict]:
        if unit_test_run_id:
            unit_run = await self.unit_test_repo.get_with_artifact(unit_test_run_id)
            if not unit_run or unit_run.requirement_id != requirement_id:
                raise NotFoundError("UnitTestRun", unit_test_run_id or "")
            if unit_run.status != UnitTestRunStatus.COMPLETED:
                raise ValidationError("Unit Test run is not completed")
        else:
            items, _ = await self.unit_test_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run for run in items if run.status == UnitTestRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Unit Test run found for this requirement. "
                    "Run Unit Test Generator first."
                )
            unit_run = completed[0]

        if not unit_run.artifacts:
            raise ValidationError("Unit Test run has no output")

        latest_artifact = sorted(unit_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return unit_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: IntegrationTestRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> IntegrationTestRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        integration_run, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            frontend_execution_run_id=data.frontend_execution_run_id,
            backend_execution_run_id=data.backend_execution_run_id,
            unit_test_run_id=data.unit_test_run_id,
        )

        run = await self.run_repo.get_with_artifact(integration_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        frontend_execution_run_id: str | None = None,
        backend_execution_run_id: str | None = None,
        unit_test_run_id: str | None = None,
    ) -> tuple[IntegrationTestRun, dict]:
        """Run Integration Test agent from workflow dispatcher without API permission checks."""
        fe_run_id, fe_output = await self._resolve_frontend_execution_output(
            requirement_id=requirement_id,
            frontend_execution_run_id=frontend_execution_run_id,
        )
        be_run_id, be_output = await self._resolve_backend_execution_output(
            requirement_id=requirement_id,
            backend_execution_run_id=backend_execution_run_id,
        )
        unit_run_id, unit_output = await self._resolve_unit_test_output(
            requirement_id=requirement_id,
            unit_test_run_id=unit_test_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            frontend_execution_run_id=fe_run_id,
            backend_execution_run_id=be_run_id,
            unit_test_run_id=unit_run_id,
            status=IntegrationTestRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="integration_test_started",
            resource_type="integration_test_run",
            resource_id=run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "frontend_execution_run_id": fe_run_id,
                "backend_execution_run_id": be_run_id,
                "unit_test_run_id": unit_run_id,
            },
        )

        await self.run_repo.update(run, status=IntegrationTestRunStatus.RUNNING)

        try:
            agent = IntegrationTestAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                frontend_execution_output=fe_output,
                backend_execution_output=be_output,
                unit_test_output=unit_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=IntegrationTestRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="integration_test_failed",
                resource_type="integration_test_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="integration_test_validated",
                resource_type="integration_test_run",
                resource_id=run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                run,
                status=IntegrationTestRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="integration_test_failed",
                resource_type="integration_test_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(f"Integration Test output failed validation (score: {validation.score})")

        await self.audit_repo.log(
            action="integration_test_validated",
            resource_type="integration_test_run",
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
            status=IntegrationTestRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="integration_test_completed",
            resource_type="integration_test_run",
            resource_id=run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> IntegrationTestRunResponse:
        run = await get_integration_test_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> IntegrationTestArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("IntegrationTestArtifact", artifact_id)
        return IntegrationTestArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> IntegrationTestRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return IntegrationTestRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
