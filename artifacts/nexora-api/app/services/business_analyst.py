from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.business_analyst import BusinessAnalystAgent
from app.auth.org_context import OrgContext
from app.business_analyst.markdown import output_to_markdown
from app.business_analyst.prompt_builder import BusinessAnalystPromptBuilder
from app.business_analyst.validator import BusinessAnalystValidator
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.agent import AgentRunStatus, AgentType
from app.models.business_analyst import BusinessAnalystRun, BusinessAnalystRunStatus
from app.models.user import User
from app.repositories.agent import AgentRunRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.business_analyst import (
    BusinessAnalystArtifactRepository,
    BusinessAnalystRunRepository,
)
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository
from app.schemas.business_analyst import (
    BusinessAnalystArtifactResponse,
    BusinessAnalystRunListResponse,
    BusinessAnalystRunRequest,
    BusinessAnalystRunResponse,
)
from app.tenancy.guards import get_business_analyst_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class BusinessAnalystService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = BusinessAnalystRunRepository(session)
        self.artifact_repo = BusinessAnalystArtifactRepository(session)
        self.agent_run_repo = AgentRunRepository(session)
        self.requirement_repo = RequirementRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = BusinessAnalystValidator()
        self.prompt_builder = BusinessAnalystPromptBuilder()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: BusinessAnalystRun) -> BusinessAnalystRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = BusinessAnalystArtifactResponse.model_validate(latest)
        return BusinessAnalystRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            product_owner_run_id=run.product_owner_run_id,
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

    async def _resolve_product_owner_output(
        self,
        *,
        requirement_id: str,
        product_owner_run_id: str | None,
    ) -> tuple[str, dict]:
        if product_owner_run_id:
            po_run = await self.agent_run_repo.get_with_outputs(product_owner_run_id)
            if not po_run or po_run.requirement_id != requirement_id:
                raise NotFoundError("AgentRun", product_owner_run_id or "")
            if po_run.status != AgentRunStatus.COMPLETED:
                raise ValidationError("Product Owner run is not completed")
        else:
            po_run = await self.agent_run_repo.get_latest_for_requirement(
                requirement_id, agent_type=AgentType.PRODUCT_OWNER
            )
            if not po_run:
                raise ValidationError(
                    "No completed Product Owner run found for this requirement. Run Product Owner first."
                )

        if not po_run.outputs:
            raise ValidationError("Product Owner run has no output")

        latest_output = sorted(po_run.outputs, key=lambda item: item.version, reverse=True)[0]
        return po_run.id, latest_output.content

    async def run(
        self,
        data: BusinessAnalystRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> BusinessAnalystRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        try:
            ba_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                product_owner_run_id=data.product_owner_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(ba_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        product_owner_run_id: str | None = None,
    ) -> tuple[BusinessAnalystRun, dict]:
        """Run BA agent from workflow dispatcher without API permission checks."""
        po_run_id, po_output = await self._resolve_product_owner_output(
            requirement_id=requirement_id,
            product_owner_run_id=product_owner_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        ba_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            product_owner_run_id=po_run_id,
            status=BusinessAnalystRunStatus.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
        )

        await self.audit_repo.log(
            action="business_analyst_started",
            resource_type="business_analyst_run",
            resource_id=ba_run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, "product_owner_run_id": po_run_id},
        )

        await self.run_repo.update(ba_run, status=BusinessAnalystRunStatus.RUNNING)

        try:
            agent = BusinessAnalystAgent()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                product_owner_output=po_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                ba_run,
                status=BusinessAnalystRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="business_analyst_failed",
                resource_type="business_analyst_run",
                resource_id=ba_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action="business_analyst_validated",
                resource_type="business_analyst_run",
                resource_id=ba_run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                ba_run,
                status=BusinessAnalystRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="business_analyst_failed",
                resource_type="business_analyst_run",
                resource_id=ba_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Business Analyst output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action="business_analyst_validated",
            resource_type="business_analyst_run",
            resource_id=ba_run.id,
            user_id=user.id,
            details={"score": validation.score, "counts": validation.counts},
        )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

        await self.artifact_repo.create(
            run_id=ba_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            validation_score=validation.score,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            ba_run,
            status=BusinessAnalystRunStatus.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="business_analyst_completed",
            resource_type="business_analyst_run",
            resource_id=ba_run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return ba_run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> BusinessAnalystRunResponse:
        run = await get_business_analyst_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> BusinessAnalystArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("BusinessAnalystArtifact", artifact_id)
        return BusinessAnalystArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> BusinessAnalystRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return BusinessAnalystRunListResponse(
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
    ) -> BusinessAnalystRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return BusinessAnalystRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
