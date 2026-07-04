import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.product_owner import ProductOwnerAgent
from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError
from app.core.logging import get_logger
from app.models.agent import AgentRunStatus, AgentType
from app.models.requirement import RequirementStatus
from app.models.user import User
from app.repositories.agent import AgentOutputRepository, AgentRunRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.requirement import RequirementRepository
from app.schemas.agent import AgentRunRequest, AgentRunResponse, ProductOwnerOutput
from app.tenancy.guards import get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class AgentWorkflowEngine:
    """
    Orchestrates the end-to-end agent workflow:
    Requirement Submitted → Agent Triggered → Generate Analysis → Store Output → Return Response
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.req_repo = RequirementRepository(session)
        self.run_repo = AgentRunRepository(session)
        self.output_repo = AgentOutputRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def execute(
        self, data: AgentRunRequest, current_user: User, org_context: OrgContext
    ) -> AgentRunResponse:
        requirement = await get_requirement_for_org(
            self.session, data.requirement_id, org_context
        )
        if requirement.submitted_by != current_user.id and not current_user.is_superuser:
            if not org_context.role or not can_write_resources(org_context.role):
                raise ForbiddenError("You don't have access to this requirement")

        agent_run = await self.run_repo.create(
            agent_type=data.agent_type,
            status=AgentRunStatus.QUEUED,
            requirement_id=data.requirement_id,
            triggered_by=current_user.id,
            model_used=settings.ANTHROPIC_MODEL,
        )

        await self.req_repo.update(requirement, status=RequirementStatus.PROCESSING)

        logger.info(
            "workflow_start",
            run_id=agent_run.id,
            requirement_id=data.requirement_id,
            agent_type=data.agent_type,
        )

        await self.run_repo.update(agent_run, status=AgentRunStatus.RUNNING)
        start_time = time.monotonic()

        output: ProductOwnerOutput | None = None
        try:
            agent_output, tokens_used = await self._dispatch_agent(
                data.agent_type, requirement.content
            )
            output = agent_output

            duration_ms = int((time.monotonic() - start_time) * 1000)

            agent_output_record = await self.output_repo.create(
                agent_run_id=agent_run.id,
                output_type="product_owner_analysis",
                content=agent_output.model_dump(),
                version=1,
            )

            await self.run_repo.update(
                agent_run,
                status=AgentRunStatus.COMPLETED,
                duration_ms=duration_ms,
                tokens_used=tokens_used,
            )

            await self.req_repo.update(requirement, status=RequirementStatus.COMPLETED)

            await self.audit_repo.log(
                action="agent.run.completed",
                resource_type="agent_run",
                resource_id=agent_run.id,
                user_id=current_user.id,
                details={
                    "duration_ms": duration_ms,
                    "tokens_used": tokens_used,
                    "epics_count": len(agent_output.epics),
                },
            )

            logger.info(
                "workflow_complete",
                run_id=agent_run.id,
                duration_ms=duration_ms,
                tokens_used=tokens_used,
            )

        except AgentError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self.run_repo.update(
                agent_run,
                status=AgentRunStatus.FAILED,
                error_message=str(e),
                duration_ms=duration_ms,
            )
            await self.req_repo.update(requirement, status=RequirementStatus.FAILED)

            await self.audit_repo.log(
                action="agent.run.failed",
                resource_type="agent_run",
                resource_id=agent_run.id,
                user_id=current_user.id,
                details={"error": str(e)},
                status="failure",
            )

            logger.error("workflow_failed", run_id=agent_run.id, error=str(e))
            raise

        run_response = AgentRunResponse.model_validate(agent_run)
        run_response.output = output
        return run_response

    async def _dispatch_agent(
        self, agent_type: AgentType, requirement_content: str
    ) -> tuple[ProductOwnerOutput, int]:
        if agent_type == AgentType.PRODUCT_OWNER:
            agent = ProductOwnerAgent()
            return await agent.run(requirement_content)
        raise AgentError(f"Agent type '{agent_type}' is not implemented yet")
