from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.ai_agent import (
    AIAgentInputRepository,
    AIAgentOutputRepository,
    AIAgentResponsibilityRepository,
    AIAgentWorkflowAssignmentRepository,
)
from app.repositories.audit import AuditLogRepository
from app.schemas.ai_agent import (
    AIAgentAssignmentCreate,
    AIAgentAssignmentResponse,
    AIAgentInputCreate,
    AIAgentInputResponse,
    AIAgentInputUpdate,
    AIAgentOutputCreate,
    AIAgentOutputResponse,
    AIAgentOutputUpdate,
    AIAgentResponsibilityCreate,
    AIAgentResponsibilityResponse,
    AIAgentResponsibilityUpdate,
)
from app.services.ai_agent import AIAgentService
from app.tenancy.guards import get_ai_agent_for_org, get_stage_for_org, get_team_for_org
from app.tenancy.permissions import can_write_ai_agents


class AIAgentComponentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.input_repo = AIAgentInputRepository(session)
        self.output_repo = AIAgentOutputRepository(session)
        self.responsibility_repo = AIAgentResponsibilityRepository(session)
        self.assignment_repo = AIAgentWorkflowAssignmentRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.agent_service = AIAgentService(session)

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_ai_agents(org_context.role)
        ):
            raise ForbiddenError()

    async def create_input(
        self,
        agent_id: str,
        data: AIAgentInputCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentInputResponse:
        await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        item = await self.input_repo.create(
            agent_id=agent_id,
            input_name=data.input_name,
            input_type=data.input_type,
            required=data.required,
        )
        await self.audit_repo.log(
            action="input_created",
            resource_type="ai_agent_input",
            resource_id=item.id,
            user_id=current_user.id,
            details={"agent_id": agent_id, "input_id": item.id},
        )
        return AIAgentInputResponse.model_validate(item)

    async def update_input(
        self,
        input_id: str,
        data: AIAgentInputUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentInputResponse:
        self._ensure_write(current_user, org_context)
        item = await self._get_input_for_org(input_id, org_context)
        updated = await self.input_repo.update(item, **data.model_dump(exclude_none=True))
        return AIAgentInputResponse.model_validate(updated)

    async def delete_input(
        self, input_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        self._ensure_write(current_user, org_context)
        item = await self._get_input_for_org(input_id, org_context)
        await self.input_repo.hard_delete(item)

    async def create_output(
        self,
        agent_id: str,
        data: AIAgentOutputCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentOutputResponse:
        await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        item = await self.output_repo.create(
            agent_id=agent_id,
            output_name=data.output_name,
            output_type=data.output_type,
        )
        await self.audit_repo.log(
            action="output_created",
            resource_type="ai_agent_output",
            resource_id=item.id,
            user_id=current_user.id,
            details={"agent_id": agent_id, "output_id": item.id},
        )
        return AIAgentOutputResponse.model_validate(item)

    async def update_output(
        self,
        output_id: str,
        data: AIAgentOutputUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentOutputResponse:
        self._ensure_write(current_user, org_context)
        item = await self._get_output_for_org(output_id, org_context)
        updated = await self.output_repo.update(item, **data.model_dump(exclude_none=True))
        return AIAgentOutputResponse.model_validate(updated)

    async def delete_output(
        self, output_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        self._ensure_write(current_user, org_context)
        item = await self._get_output_for_org(output_id, org_context)
        await self.output_repo.hard_delete(item)

    async def create_responsibility(
        self,
        agent_id: str,
        data: AIAgentResponsibilityCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentResponsibilityResponse:
        await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        item = await self.responsibility_repo.create(
            agent_id=agent_id,
            title=data.title,
            description=data.description,
            priority=data.priority,
        )
        await self.audit_repo.log(
            action="responsibility_created",
            resource_type="ai_agent_responsibility",
            resource_id=item.id,
            user_id=current_user.id,
            details={"agent_id": agent_id, "responsibility_id": item.id},
        )
        return AIAgentResponsibilityResponse.model_validate(item)

    async def update_responsibility(
        self,
        responsibility_id: str,
        data: AIAgentResponsibilityUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentResponsibilityResponse:
        self._ensure_write(current_user, org_context)
        item = await self._get_responsibility_for_org(responsibility_id, org_context)
        updated = await self.responsibility_repo.update(item, **data.model_dump(exclude_none=True))
        return AIAgentResponsibilityResponse.model_validate(updated)

    async def delete_responsibility(
        self, responsibility_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        self._ensure_write(current_user, org_context)
        item = await self._get_responsibility_for_org(responsibility_id, org_context)
        await self.responsibility_repo.hard_delete(item)

    async def assign_to_stage(
        self,
        agent_id: str,
        data: AIAgentAssignmentCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentAssignmentResponse:
        await get_ai_agent_for_org(self.session, agent_id, org_context)
        await get_stage_for_org(self.session, data.workflow_stage_id, org_context)
        if data.team_id:
            await get_team_for_org(self.session, data.team_id, org_context)
        self._ensure_write(current_user, org_context)

        existing = await self.assignment_repo.get_assignment(
            agent_id, data.workflow_stage_id, data.team_id
        )
        if existing:
            raise ConflictError("Agent is already assigned to this stage/team combination")

        assignment = await self.assignment_repo.create(
            agent_id=agent_id,
            workflow_stage_id=data.workflow_stage_id,
            team_id=data.team_id,
            execution_order=data.execution_order,
            is_required=data.is_required,
        )
        await self.audit_repo.log(
            action="agent_assigned",
            resource_type="ai_agent_workflow_assignment",
            resource_id=assignment.id,
            user_id=current_user.id,
            details={
                "agent_id": agent_id,
                "workflow_stage_id": data.workflow_stage_id,
                "team_id": data.team_id,
            },
        )
        loaded = await self.assignment_repo.get_with_details(assignment.id)
        return self.agent_service._assignment_response(loaded)

    async def unassign(
        self,
        agent_id: str,
        assignment_id: str,
        current_user: User,
        org_context: OrgContext,
    ) -> None:
        await get_ai_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        assignment = await self.assignment_repo.get_with_details(assignment_id)
        if not assignment or assignment.agent_id != agent_id:
            raise NotFoundError("AIAgentWorkflowAssignment", assignment_id)
        await get_stage_for_org(self.session, assignment.workflow_stage_id, org_context)
        await self.assignment_repo.hard_delete(assignment)

    async def _get_input_for_org(self, input_id: str, org_context: OrgContext):
        item = await self.input_repo.get_by_id(input_id)
        if not item:
            raise NotFoundError("AIAgentInput", input_id)
        await get_ai_agent_for_org(self.session, item.agent_id, org_context)
        return item

    async def _get_output_for_org(self, output_id: str, org_context: OrgContext):
        item = await self.output_repo.get_by_id(output_id)
        if not item:
            raise NotFoundError("AIAgentOutput", output_id)
        await get_ai_agent_for_org(self.session, item.agent_id, org_context)
        return item

    async def _get_responsibility_for_org(self, responsibility_id: str, org_context: OrgContext):
        item = await self.responsibility_repo.get_by_id(responsibility_id)
        if not item:
            raise NotFoundError("AIAgentResponsibility", responsibility_id)
        await get_ai_agent_for_org(self.session, item.agent_id, org_context)
        return item
