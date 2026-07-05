from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.ai_agent import AIAgent, AIAgentStatus
from app.models.user import User
from app.repositories.ai_agent import (
    AIAgentInputRepository,
    AIAgentOutputRepository,
    AIAgentRepository,
    AIAgentResponsibilityRepository,
    AIAgentWorkflowAssignmentRepository,
)
from app.repositories.audit import AuditLogRepository
from app.schemas.ai_agent import (
    AIAgentAssignmentResponse,
    AIAgentAuditEventResponse,
    AIAgentAuditListResponse,
    AIAgentCreate,
    AIAgentDuplicateResponse,
    AIAgentInputResponse,
    AIAgentListResponse,
    AIAgentOutputResponse,
    AIAgentResponse,
    AIAgentResponsibilityResponse,
    AIAgentUpdate,
)
from app.tenancy.guards import get_ai_agent_for_org
from app.tenancy.permissions import can_manage_ai_agents, can_read_ai_agents, can_write_ai_agents

logger = get_logger(__name__)


class AIAgentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_repo = AIAgentRepository(session)
        self.input_repo = AIAgentInputRepository(session)
        self.output_repo = AIAgentOutputRepository(session)
        self.responsibility_repo = AIAgentResponsibilityRepository(session)
        self.assignment_repo = AIAgentWorkflowAssignmentRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_ai_agents(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_ai_agents(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_manage(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_manage_ai_agents(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, agent: AIAgent) -> AIAgentResponse:
        assignments = sorted(agent.workflow_assignments or [], key=lambda item: item.execution_order)
        return AIAgentResponse(
            id=agent.id,
            organization_id=agent.organization_id,
            name=agent.name,
            description=agent.description,
            goal=agent.goal,
            status=agent.status,
            prompt_template=agent.prompt_template,
            created_by=agent.created_by,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            input_count=len(agent.inputs or []),
            output_count=len(agent.outputs or []),
            responsibility_count=len(agent.responsibilities or []),
            assignment_count=len(assignments),
            inputs=[AIAgentInputResponse.model_validate(item) for item in agent.inputs or []],
            outputs=[AIAgentOutputResponse.model_validate(item) for item in agent.outputs or []],
            responsibilities=[
                AIAgentResponsibilityResponse.model_validate(item)
                for item in agent.responsibilities or []
            ],
            workflow_assignments=[
                self._assignment_response(assignment) for assignment in assignments
            ],
        )

    def _assignment_response(self, assignment) -> AIAgentAssignmentResponse:
        stage = assignment.stage
        workflow = stage.workflow if stage else None
        return AIAgentAssignmentResponse(
            id=assignment.id,
            agent_id=assignment.agent_id,
            workflow_stage_id=assignment.workflow_stage_id,
            workflow_stage_name=stage.name if stage else None,
            workflow_id=workflow.id if workflow else None,
            workflow_name=workflow.name if workflow else None,
            team_id=assignment.team_id,
            team_name=assignment.team.name if assignment.team else None,
            execution_order=assignment.execution_order,
            is_required=assignment.is_required,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )

    async def create(
        self, data: AIAgentCreate, current_user: User, org_context: OrgContext
    ) -> AIAgentResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        agent = await self.agent_repo.create(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            goal=data.goal,
            status=data.status,
            prompt_template=data.prompt_template,
            created_by=current_user.id,
        )
        agent = await self.agent_repo.get_with_details(agent.id)
        await self.audit_repo.log(
            action="agent_created",
            resource_type="ai_agent",
            resource_id=agent.id,
            user_id=current_user.id,
            details={"agent_id": agent.id},
        )
        logger.info("agent_created", agent_id=agent.id)
        return self._to_response(agent)

    async def list_for_organization(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        status=None,
        offset: int = 0,
        limit: int = 50,
    ) -> AIAgentListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.agent_repo.list_by_organization(
            organization_id, status=status, offset=offset, limit=limit
        )
        detailed = []
        for item in items:
            agent = await self.agent_repo.get_with_details(item.id)
            if agent:
                detailed.append(self._to_response(agent))
        return AIAgentListResponse(items=detailed, total=total)

    async def get(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> AIAgentResponse:
        agent = await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_read(current_user, org_context)
        return self._to_response(agent)

    async def update(
        self, agent_id: str, data: AIAgentUpdate, current_user: User, org_context: OrgContext
    ) -> AIAgentResponse:
        agent = await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        update_data = data.model_dump(exclude_none=True)
        updated = await self.agent_repo.update(agent, **update_data)
        agent = await self.agent_repo.get_with_details(updated.id)
        await self.audit_repo.log(
            action="agent_updated",
            resource_type="ai_agent",
            resource_id=agent_id,
            user_id=current_user.id,
            details={"agent_id": agent_id, **update_data},
        )
        return self._to_response(agent)

    async def archive(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> AIAgentResponse:
        agent = await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_manage(current_user, org_context)
        updated = await self.agent_repo.update(agent, status=AIAgentStatus.ARCHIVED)
        agent = await self.agent_repo.get_with_details(updated.id)
        await self.audit_repo.log(
            action="agent_archived",
            resource_type="ai_agent",
            resource_id=agent_id,
            user_id=current_user.id,
            details={"agent_id": agent_id},
        )
        return self._to_response(agent)

    async def delete(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        agent = await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_manage(current_user, org_context)
        await self.agent_repo.hard_delete(agent)
        await self.audit_repo.log(
            action="agent_deleted",
            resource_type="ai_agent",
            resource_id=agent_id,
            user_id=current_user.id,
            details={"agent_id": agent_id},
        )

    async def duplicate(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> AIAgentDuplicateResponse:
        source = await get_ai_agent_for_org(self.session, agent_id, org_context)
        source = await self.agent_repo.get_with_details(source.id)
        if not source:
            raise NotFoundError("AIAgent", agent_id)
        self._ensure_write(current_user, org_context)

        duplicate = await self.agent_repo.create(
            organization_id=source.organization_id,
            name=f"{source.name} (Copy)",
            description=source.description,
            goal=source.goal,
            status=AIAgentStatus.DRAFT,
            prompt_template=source.prompt_template,
            created_by=current_user.id,
        )

        for item in source.inputs or []:
            await self.input_repo.create(
                agent_id=duplicate.id,
                input_name=item.input_name,
                input_type=item.input_type,
                required=item.required,
            )
        for item in source.outputs or []:
            await self.output_repo.create(
                agent_id=duplicate.id,
                output_name=item.output_name,
                output_type=item.output_type,
            )
        for item in source.responsibilities or []:
            await self.responsibility_repo.create(
                agent_id=duplicate.id,
                title=item.title,
                description=item.description,
                priority=item.priority,
            )

        agent = await self.agent_repo.get_with_details(duplicate.id)
        await self.audit_repo.log(
            action="agent_duplicated",
            resource_type="ai_agent",
            resource_id=duplicate.id,
            user_id=current_user.id,
            details={"agent_id": duplicate.id, "source_agent_id": agent_id},
        )
        return AIAgentDuplicateResponse(agent=self._to_response(agent))

    async def list_audit_events(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> AIAgentAuditListResponse:
        await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.audit_repo.list_for_ai_agent(agent_id)
        return AIAgentAuditListResponse(
            items=[AIAgentAuditEventResponse.model_validate(item) for item in items],
            total=total,
        )
