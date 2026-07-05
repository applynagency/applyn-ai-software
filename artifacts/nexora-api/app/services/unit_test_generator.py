from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.unit_test_generator import UnitTestGeneratorAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.qa_architect import QAArchitectRunStatus
from app.models.unit_test import UnitTestRun, UnitTestRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.project import ProjectRepository
from app.repositories.qa_architect import QAArchitectRunRepository
from app.repositories.unit_test import UnitTestArtifactRepository, UnitTestRunRepository
from app.schemas.unit_test import (
    UnitTestArtifactResponse,
    UnitTestRunListResponse,
    UnitTestRunRequest,
    UnitTestRunResponse,
)
from app.tenancy.guards import get_requirement_for_org, get_unit_test_run_for_org
from app.tenancy.permissions import can_write_resources
from app.unit_test_generator.markdown import output_to_markdown
from app.unit_test_generator.prompt_builder import UnitTestGeneratorPromptBuilder
from app.unit_test_generator.validator import UnitTestGeneratorValidator

logger = get_logger(__name__)


class UnitTestGeneratorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = UnitTestRunRepository(session)
        self.artifact_repo = UnitTestArtifactRepository(session)
        self.qa_run_repo = QAArchitectRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = UnitTestGeneratorValidator()
        self.prompt_builder = UnitTestGeneratorPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: UnitTestRun) -> UnitTestRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = UnitTestArtifactResponse.model_validate(latest)
        return UnitTestRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            qa_architect_run_id=run.qa_architect_run_id,
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

    async def _resolve_qa_architect_output(
        self,
        *,
        requirement_id: str,
        qa_architect_run_id: str | None,
    ) -> tuple[str, dict]:
        if qa_architect_run_id:
            qa_run = await self.qa_run_repo.get_with_artifact(qa_architect_run_id)
            if not qa_run or qa_run.requirement_id != requirement_id:
                raise NotFoundError("QAArchitectRun", qa_architect_run_id or "")
            if qa_run.status != QAArchitectRunStatus.COMPLETED:
                raise ValidationError("QA Architect run is not completed")
        else:
            items, _ = await self.qa_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == QAArchitectRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed QA Architect run found for this requirement. "
                    "Run QA Architect first."
                )
            qa_run = completed[0]

        if not qa_run.artifacts:
            raise ValidationError("QA Architect run has no output")

        latest_artifact = sorted(qa_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return qa_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: UnitTestRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> UnitTestRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        try:
            unit_test_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                qa_architect_run_id=data.qa_architect_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(unit_test_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        qa_architect_run_id: str | None = None,
    ) -> tuple[UnitTestRun, dict]:
        """Run Unit Test Generator agent from workflow dispatcher without API permission checks."""
        qa_run_id, qa_output = await self._resolve_qa_architect_output(
            requirement_id=requirement_id,
            qa_architect_run_id=qa_architect_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            qa_architect_run_id=qa_run_id,
            status=UnitTestRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="unit_test_started",
            resource_type="unit_test_run",
            resource_id=run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "qa_architect_run_id": qa_run_id},
        )

        await self.run_repo.update(run, status=UnitTestRunStatus.RUNNING)

        try:
            agent = UnitTestGeneratorAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                qa_architect_output=qa_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=UnitTestRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="unit_test_failed",
                resource_type="unit_test_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="unit_test_validated",
                resource_type="unit_test_run",
                resource_id=run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                run,
                status=UnitTestRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="unit_test_failed",
                resource_type="unit_test_run",
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(
                f"Unit Test Generator output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="unit_test_validated",
            resource_type="unit_test_run",
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
            status=UnitTestRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="unit_test_completed",
            resource_type="unit_test_run",
            resource_id=run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> UnitTestRunResponse:
        run = await get_unit_test_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> UnitTestArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("UnitTestArtifact", artifact_id)
        return UnitTestArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> UnitTestRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return UnitTestRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
