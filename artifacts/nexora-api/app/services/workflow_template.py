from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.team import TeamStatus, TeamType
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.team import TeamAgentMappingRepository, TeamRepository
from app.repositories.workflow import (
    WorkflowRepository,
    WorkflowRuleRepository,
    WorkflowStageRepository,
    WorkflowStageTeamRepository,
)
from app.schemas.workflow import (
    WorkflowTemplateApplyRequest,
    WorkflowTemplateApplyResponse,
    WorkflowTemplateListResponse,
    WorkflowTemplateResponse,
    WorkflowTemplateStagePreview,
)
from app.services.workflow import WorkflowService
from app.teams.mappings import TeamMappingService
from app.tenancy.permissions import can_read_workflows, can_write_workflows
from app.workflows.rules_engine import WorkflowRulesEngine
from app.workflows.templates import (
    WORKFLOW_TEMPLATES,
    get_template_by_slug,
    get_template_definition,
)

logger = get_logger(__name__)


class WorkflowTemplateService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow_repo = WorkflowRepository(session)
        self.stage_repo = WorkflowStageRepository(session)
        self.assignment_repo = WorkflowStageTeamRepository(session)
        self.rule_repo = WorkflowRuleRepository(session)
        self.team_repo = TeamRepository(session)
        self.mapping_repo = TeamAgentMappingRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.mapping_service = TeamMappingService()
        self.rules_engine = WorkflowRulesEngine()
        self.workflow_service = WorkflowService(session)

    async def _find_or_create_team(
        self,
        organization_id: str,
        user_id: str,
        name: str,
        team_type: str,
    ):
        teams, _ = await self.team_repo.list_by_organization(organization_id, limit=500)
        for team in teams:
            if team.name == name:
                return team
        team = await self.team_repo.create(
            organization_id=organization_id,
            name=name,
            description="Auto-created for workflow template",
            team_type=TeamType(team_type),
            status=TeamStatus.ACTIVE,
            created_by=user_id,
        )
        specs = self.mapping_service.mapping_specs_for_team_type(team.team_type)
        if specs:
            await self.mapping_repo.replace_for_team(team.id, specs)
        return team

    async def list_templates(
        self, current_user: User, org_context: OrgContext, *, include_definition: bool = False
    ) -> WorkflowTemplateListResponse:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_workflows(org_context.role)
        ):
            raise ForbiddenError()
        items = [
            WorkflowTemplateResponse(
                slug=template.slug,
                name=template.name,
                description=template.description,
                industry=template.industry,
                stage_count=len(template.stages),
                stages=[
                    WorkflowTemplateStagePreview(
                        name=stage.name,
                        sequence=stage.sequence,
                        stage_type=stage.stage_type,
                        team_count=len(stage.teams),
                    )
                    for stage in template.stages
                ],
                definition=get_template_definition(template.slug) if include_definition else None,
            )
            for template in WORKFLOW_TEMPLATES
        ]
        return WorkflowTemplateListResponse(items=items, total=len(items))

    async def get_template(
        self, slug: str, current_user: User, org_context: OrgContext
    ) -> WorkflowTemplateResponse:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_workflows(org_context.role)
        ):
            raise ForbiddenError()
        template = get_template_by_slug(slug)
        if not template:
            raise NotFoundError("WorkflowTemplate", slug)
        return WorkflowTemplateResponse(
            slug=template.slug,
            name=template.name,
            description=template.description,
            industry=template.industry,
            stage_count=len(template.stages),
            stages=[
                WorkflowTemplateStagePreview(
                    name=stage.name,
                    sequence=stage.sequence,
                    stage_type=stage.stage_type,
                    team_count=len(stage.teams),
                )
                for stage in template.stages
            ],
            definition=get_template_definition(slug),
        )

    async def apply_template(
        self,
        data: WorkflowTemplateApplyRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> WorkflowTemplateApplyResponse:
        organization_id = org_context.requires_organization
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()

        template = get_template_by_slug(data.template_slug)
        if not template:
            raise NotFoundError("WorkflowTemplate", data.template_slug)

        workflow = await self.workflow_repo.create(
            organization_id=organization_id,
            name=template.workflow_name,
            description=template.workflow_description,
            status=template.workflow_status,
            is_default=False,
            created_by=current_user.id,
        )

        for stage_template in template.stages:
            stage = await self.stage_repo.create(
                workflow_id=workflow.id,
                name=stage_template.name,
                description=stage_template.description,
                sequence=stage_template.sequence,
                stage_type=stage_template.stage_type,
                approval_required=stage_template.approval_required,
            )
            for team_template in stage_template.teams:
                team = await self._find_or_create_team(
                    organization_id,
                    current_user.id,
                    team_template.name,
                    team_template.team_type,
                )
                await self.assignment_repo.create(
                    workflow_stage_id=stage.id,
                    team_id=team.id,
                    execution_order=team_template.execution_order,
                    is_required=team_template.is_required,
                )

        for rule_template in template.rules:
            configuration = self.rules_engine.validate_rule(
                rule_template.rule_type, rule_template.configuration_json
            )
            await self.rule_repo.create(
                workflow_id=workflow.id,
                rule_type=rule_template.rule_type,
                configuration_json=configuration,
            )

        loaded = await self.workflow_repo.get_with_details(workflow.id)
        await self.audit_repo.log(
            action="workflow_template_applied",
            resource_type="workflow_template",
            resource_id=data.template_slug,
            user_id=current_user.id,
            details={"workflow_id": workflow.id, "template_slug": data.template_slug},
        )
        logger.info(
            "workflow_template_applied",
            template_slug=data.template_slug,
            workflow_id=workflow.id,
        )
        return WorkflowTemplateApplyResponse(
            template_slug=data.template_slug,
            workflow=self.workflow_service._to_response(loaded),
        )
