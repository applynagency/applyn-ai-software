from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.qa_approval import QAApprovalAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.integration_test import IntegrationTestRunStatus
from app.models.performance_test import PerformanceTestRunStatus
from app.models.qa_approval import QAApprovalRun, QAApprovalRunStatus, QAStatus
from app.models.security_test import SecurityTestRunStatus
from app.models.user import User
from app.qa_approval.markdown import output_to_markdown
from app.qa_approval.prompt_builder import QAApprovalPromptBuilder
from app.qa_approval.validator import QAApprovalValidator
from app.repositories.audit import AuditLogRepository
from app.repositories.integration_test import IntegrationTestRunRepository
from app.repositories.performance_test import PerformanceTestRunRepository
from app.repositories.project import ProjectRepository
from app.repositories.qa_approval import QAApprovalArtifactRepository, QAApprovalRunRepository
from app.repositories.security_test import SecurityTestRunRepository
from app.schemas.qa_approval import (
    QAApprovalArtifactResponse,
    QAApprovalRunListResponse,
    QAApprovalRunRequest,
    QAApprovalRunResponse,
)
from app.tenancy.guards import get_qa_approval_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class QAApprovalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = QAApprovalRunRepository(session)
        self.artifact_repo = QAApprovalArtifactRepository(session)
        self.integration_test_repo = IntegrationTestRunRepository(session)
        self.security_test_repo = SecurityTestRunRepository(session)
        self.performance_test_repo = PerformanceTestRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = QAApprovalValidator()
        self.prompt_builder = QAApprovalPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: QAApprovalRun) -> QAApprovalRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = QAApprovalArtifactResponse.model_validate(latest)
        return QAApprovalRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            integration_test_run_id=run.integration_test_run_id,
            security_test_run_id=run.security_test_run_id,
            performance_test_run_id=run.performance_test_run_id,
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

    async def _resolve_integration_test_output(
        self,
        *,
        requirement_id: str,
        integration_test_run_id: str | None,
    ) -> tuple[str, dict]:
        if integration_test_run_id:
            integration_run = await self.integration_test_repo.get_with_artifact(integration_test_run_id)
            if not integration_run or integration_run.requirement_id != requirement_id:
                raise NotFoundError("IntegrationTestRun", integration_test_run_id or "")
            if integration_run.status != IntegrationTestRunStatus.COMPLETED:
                raise ValidationError("Integration Test run is not completed")
        else:
            items, _ = await self.integration_test_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == IntegrationTestRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Integration Test run found for this requirement. "
                    "Run Integration Test first."
                )
            integration_run = completed[0]

        if not integration_run.artifacts:
            raise ValidationError("Integration Test run has no output")

        latest_artifact = sorted(
            integration_run.artifacts, key=lambda item: item.created_at, reverse=True
        )[0]
        return integration_run.id, latest_artifact.artifact_json

    async def _resolve_security_test_output(
        self,
        *,
        requirement_id: str,
        security_test_run_id: str | None,
    ) -> tuple[str, dict]:
        if security_test_run_id:
            security_run = await self.security_test_repo.get_with_artifact(security_test_run_id)
            if not security_run or security_run.requirement_id != requirement_id:
                raise NotFoundError("SecurityTestRun", security_test_run_id or "")
            if security_run.status != SecurityTestRunStatus.COMPLETED:
                raise ValidationError("Security Test run is not completed")
        else:
            items, _ = await self.security_test_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run for run in items if run.status == SecurityTestRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Security Test run found for this requirement. "
                    "Run Security Test first."
                )
            security_run = completed[0]

        if not security_run.artifacts:
            raise ValidationError("Security Test run has no output")

        latest_artifact = sorted(security_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return security_run.id, latest_artifact.artifact_json

    async def _resolve_performance_test_output(
        self,
        *,
        requirement_id: str,
        performance_test_run_id: str | None,
    ) -> tuple[str, dict]:
        if performance_test_run_id:
            performance_run = await self.performance_test_repo.get_with_artifact(performance_test_run_id)
            if not performance_run or performance_run.requirement_id != requirement_id:
                raise NotFoundError("PerformanceTestRun", performance_test_run_id or "")
            if performance_run.status != PerformanceTestRunStatus.COMPLETED:
                raise ValidationError("Performance Test run is not completed")
        else:
            items, _ = await self.performance_test_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == PerformanceTestRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Performance Test run found for this requirement. "
                    "Run Performance Test first."
                )
            performance_run = completed[0]

        if not performance_run.artifacts:
            raise ValidationError("Performance Test run has no output")

        latest_artifact = sorted(
            performance_run.artifacts, key=lambda item: item.created_at, reverse=True
        )[0]
        return performance_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: QAApprovalRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> QAApprovalRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        approval_run, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            integration_test_run_id=data.integration_test_run_id,
            security_test_run_id=data.security_test_run_id,
            performance_test_run_id=data.performance_test_run_id,
        )

        run = await self.run_repo.get_with_artifact(approval_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        integration_test_run_id: str | None = None,
        security_test_run_id: str | None = None,
        performance_test_run_id: str | None = None,
    ) -> tuple[QAApprovalRun, dict]:
        """Run QA Approval agent from workflow dispatcher without API permission checks."""
        integration_run_id, integration_output = await self._resolve_integration_test_output(
            requirement_id=requirement_id,
            integration_test_run_id=integration_test_run_id,
        )
        security_run_id, security_output = await self._resolve_security_test_output(
            requirement_id=requirement_id,
            security_test_run_id=security_test_run_id,
        )
        performance_run_id, performance_output = await self._resolve_performance_test_output(
            requirement_id=requirement_id,
            performance_test_run_id=performance_test_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            integration_test_run_id=integration_run_id,
            security_test_run_id=security_run_id,
            performance_test_run_id=performance_run_id,
            status=QAApprovalRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="qa_approval_started",
            resource_type="qa_approval_run",
            resource_id=run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "integration_test_run_id": integration_run_id,
                "security_test_run_id": security_run_id,
                "performance_test_run_id": performance_run_id,
            },
        )

        await self.run_repo.update(run, status=QAApprovalRunStatus.RUNNING)

        try:
            agent = QAApprovalAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                integration_test_output=integration_output,
                security_test_output=security_output,
                performance_test_output=performance_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=QAApprovalRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="qa_approval_failed",
                resource_type="qa_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.run_repo.update(
                run,
                status=QAApprovalRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="qa_approval_failed",
                resource_type="qa_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(f"QA Approval output failed validation (score: {validation.score})")

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump(mode="json")

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
            status=QAApprovalRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        if output.qa_status == QAStatus.QA_REJECTED:
            await self.audit_repo.log(
                action="qa_rejected",
                resource_type="qa_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={
                    "qa_status": output.qa_status.value,
                    "quality_score": output.quality_score,
                },
                status="failure",
            )
        else:
            await self.audit_repo.log(
                action="qa_approved",
                resource_type="qa_approval_run",
                resource_id=run.id,
                user_id=user.id,
                details={
                    "qa_status": output.qa_status.value,
                    "quality_score": output.quality_score,
                },
            )

        await self.audit_repo.log(
            action="qa_approval_completed",
            resource_type="qa_approval_run",
            resource_id=run.id,
            user_id=user.id,
            details={
                "validation_score": validation.score,
                "tokens_used": tokens_used,
                "qa_status": output.qa_status.value,
                "quality_score": output.quality_score,
            },
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> QAApprovalRunResponse:
        run = await get_qa_approval_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> QAApprovalArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("QAApprovalArtifact", artifact_id)
        return QAApprovalArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> QAApprovalRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return QAApprovalRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
