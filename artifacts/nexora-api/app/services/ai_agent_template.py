from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agents.templates import (
    AI_AGENT_TEMPLATES,
    get_template_by_slug,
    get_template_definition,
)
from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.ai_agent import (
    AIAgentInputRepository,
    AIAgentOutputRepository,
    AIAgentRepository,
    AIAgentResponsibilityRepository,
)
from app.repositories.audit import AuditLogRepository
from app.schemas.ai_agent import (
    AIAgentTemplateApplyRequest,
    AIAgentTemplateApplyResponse,
    AIAgentTemplateListResponse,
    AIAgentTemplatePreview,
    AIAgentTemplateResponse,
)
from app.services.ai_agent import AIAgentService
from app.tenancy.permissions import can_read_ai_agents, can_write_ai_agents

logger = get_logger(__name__)


class AIAgentTemplateService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_repo = AIAgentRepository(session)
        self.input_repo = AIAgentInputRepository(session)
        self.output_repo = AIAgentOutputRepository(session)
        self.responsibility_repo = AIAgentResponsibilityRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.agent_service = AIAgentService(session)

    async def list_templates(
        self, current_user: User, org_context: OrgContext, *, include_definition: bool = False
    ) -> AIAgentTemplateListResponse:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_ai_agents(org_context.role)
        ):
            raise ForbiddenError()
        items = [
            AIAgentTemplateResponse(
                slug=template.slug,
                name=template.name,
                description=template.description,
                category=template.category,
                agent=AIAgentTemplatePreview(
                    name=template.agent_name,
                    goal=template.agent_goal,
                    input_count=len(template.inputs),
                    output_count=len(template.outputs),
                ),
                definition=get_template_definition(template.slug) if include_definition else None,
            )
            for template in AI_AGENT_TEMPLATES
        ]
        return AIAgentTemplateListResponse(items=items, total=len(items))

    async def get_template(
        self, slug: str, current_user: User, org_context: OrgContext
    ) -> AIAgentTemplateResponse:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_ai_agents(org_context.role)
        ):
            raise ForbiddenError()
        template = get_template_by_slug(slug)
        if not template:
            raise NotFoundError("AIAgentTemplate", slug)
        return AIAgentTemplateResponse(
            slug=template.slug,
            name=template.name,
            description=template.description,
            category=template.category,
            agent=AIAgentTemplatePreview(
                name=template.agent_name,
                goal=template.agent_goal,
                input_count=len(template.inputs),
                output_count=len(template.outputs),
            ),
            definition=get_template_definition(slug),
        )

    async def apply_template(
        self,
        data: AIAgentTemplateApplyRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> AIAgentTemplateApplyResponse:
        organization_id = org_context.requires_organization
        if not current_user.is_superuser and (
            not org_context.role or not can_write_ai_agents(org_context.role)
        ):
            raise ForbiddenError()

        template = get_template_by_slug(data.template_slug)
        if not template:
            raise NotFoundError("AIAgentTemplate", data.template_slug)

        agent = await self.agent_repo.create(
            organization_id=organization_id,
            name=template.agent_name,
            description=template.agent_description,
            goal=template.agent_goal,
            status=template.agent_status,
            prompt_template=template.prompt_template,
            created_by=current_user.id,
        )

        for item in template.inputs:
            await self.input_repo.create(
                agent_id=agent.id,
                input_name=item.input_name,
                input_type=item.input_type,
                required=item.required,
            )
        for item in template.outputs:
            await self.output_repo.create(
                agent_id=agent.id,
                output_name=item.output_name,
                output_type=item.output_type,
            )
        for item in template.responsibilities:
            await self.responsibility_repo.create(
                agent_id=agent.id,
                title=item.title,
                description=item.description,
                priority=item.priority,
            )

        loaded = await self.agent_repo.get_with_details(agent.id)
        await self.audit_repo.log(
            action="agent_template_applied",
            resource_type="ai_agent_template",
            resource_id=data.template_slug,
            user_id=current_user.id,
            details={"agent_id": agent.id, "template_slug": data.template_slug},
        )
        logger.info(
            "agent_template_applied",
            template_slug=data.template_slug,
            agent_id=agent.id,
        )
        return AIAgentTemplateApplyResponse(
            template_slug=data.template_slug,
            agent=self.agent_service._to_response(loaded),
        )
