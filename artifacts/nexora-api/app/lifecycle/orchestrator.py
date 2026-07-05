"""Customer-facing lifecycle orchestration with automatic dependency resolution."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.lifecycle.customer_messages import customer_status_message, translate_customer_error
from app.lifecycle.prerequisites import (
    DEPLOY_READINESS_CHAIN,
    AgentPrerequisiteChecker,
    chain_prefix_for_agents,
    prerequisites_for_agents,
)
from app.lifecycle.qa_gate import ASSEMBLY_QA_GATE_MESSAGE
from app.models.user import User
from app.schemas.deployment import DeploymentRunRequest, DeploymentRunResponse
from app.schemas.lifecycle import (
    ChangeRequestCreate,
    RegenerationRunResponse,
    ReleaseCreate,
    ReleaseHistoryResponse,
)
from app.services.deployment import DeploymentService
from app.services.lifecycle import LifecycleService
from app.workflows.dispatcher import AgentDispatcher

logger = get_logger(__name__)


class LifecycleOrchestratorService:
    """Resolve internal pipeline dependencies before customer lifecycle actions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.dispatcher = AgentDispatcher()
        self.checker = AgentPrerequisiteChecker(session)

    async def deploy_application(
        self,
        data: DeploymentRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> DeploymentRunResponse:
        from app.tenancy.guards import get_requirement_for_org

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        await self.ensure_deploy_prerequisites(
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
        )
        service = DeploymentService(self.session)
        response = await service.run(data, current_user, org_context)
        return response.model_copy(
            update={"customer_message": customer_status_message("deploy")}
        )

    async def ensure_deploy_prerequisites(
        self,
        *,
        requirement_id: str,
        requirement_content: str,
        user: User,
    ) -> None:
        await self._run_agent_chain(
            DEPLOY_READINESS_CHAIN,
            requirement_id=requirement_id,
            requirement_content=requirement_content,
            user=user,
        )

    async def ensure_assembly_prerequisites(
        self,
        *,
        requirement_id: str,
        requirement_content: str,
        user: User,
    ) -> None:
        chain = [
            agent
            for agent in chain_prefix_for_agents(["fullstack_assembly"])
            if agent != "fullstack_assembly"
        ]
        await self._run_agent_chain(
            chain,
            requirement_id=requirement_id,
            requirement_content=requirement_content,
            user=user,
        )
        await self._ensure_qa_approval_gate(requirement_id=requirement_id)

    async def ensure_approval_prerequisites(
        self,
        *,
        requirement_id: str,
        requirement_content: str,
        user: User,
    ) -> None:
        chain = [
            agent
            for agent in chain_prefix_for_agents(["approval"])
            if agent != "approval"
        ]
        await self._run_agent_chain(
            chain,
            requirement_id=requirement_id,
            requirement_content=requirement_content,
            user=user,
        )

    async def create_change_request(
        self,
        data: ChangeRequestCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> RegenerationRunResponse:
        service = LifecycleService(self.session)
        response = await service.create_change_request(data, current_user, org_context)
        return response.model_copy(
            update={"customer_message": customer_status_message("change_request")}
        )

    async def regenerate_version(
        self,
        run_id: str,
        current_user: User,
        org_context: OrgContext,
    ) -> RegenerationRunResponse:
        from app.repositories.lifecycle import RegenerationRunRepository
        from app.tenancy.guards import get_requirement_for_org

        run_repo = RegenerationRunRepository(self.session)
        run = await run_repo.get_with_artifacts(run_id)
        if not run:
            raise ValidationError(translate_customer_error("Regeneration run not found"))
        requirement = await get_requirement_for_org(self.session, run.requirement_id, org_context)

        target_agents = list(run.execution_plan.get("agents", []))
        prerequisite_chain = prerequisites_for_agents(target_agents)
        await self._run_agent_chain(
            prerequisite_chain,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
        )

        service = LifecycleService(self.session)
        response = await service.execute_regeneration(run_id, current_user, org_context)
        return response.model_copy(
            update={
                "customer_message": customer_status_message(
                    "regenerate",
                    version=response.target_version,
                )
            }
        )

    async def create_release(
        self,
        data: ReleaseCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> ReleaseHistoryResponse:
        service = LifecycleService(self.session)
        if data.regeneration_run_id:
            regeneration = await service.get_regeneration_run(
                data.regeneration_run_id, current_user, org_context
            )
            run_id = regeneration.id
            target_version = regeneration.target_version
        else:
            change_request = await service.create_change_request(
                ChangeRequestCreate(
                    requirement_id=data.requirement_id,
                    title=data.title,
                    description=data.description,
                    scope=data.scope,
                ),
                current_user,
                org_context,
            )
            run_id = change_request.id
            target_version = change_request.target_version

        regeneration = await self.regenerate_version(run_id, current_user, org_context)
        status = regeneration.status.value if hasattr(regeneration.status, "value") else regeneration.status
        if status != "COMPLETED":
            raise ValidationError(
                translate_customer_error(regeneration.error_message or "Release could not complete")
            )

        releases = await service.list_releases(
            regeneration.project_id,
            current_user,
            org_context,
            limit=5,
        )
        latest = releases.items[0] if releases.items else None
        if not latest:
            raise ValidationError(translate_customer_error("Release record was not created"))

        return ReleaseHistoryResponse.model_validate(latest).model_copy(
            update={
                "customer_message": customer_status_message("release", version=target_version)
            }
        )

    async def _run_agent_chain(
        self,
        agents: list[str],
        *,
        requirement_id: str,
        requirement_content: str,
        user: User,
    ) -> None:
        for agent in agents:
            if await self.checker.is_satisfied(agent, requirement_id):
                continue
            logger.info(
                "lifecycle_orchestrator_dispatch",
                requirement_id=requirement_id,
                agent=agent,
            )
            result = await self.dispatcher.dispatch_internal(
                internal_agent=agent,
                requirement_content=requirement_content,
                session=self.session,
                requirement_id=requirement_id,
                user=user,
            )
            if result.status != "completed":
                raw = result.error_message or f"Build step did not complete ({result.status})"
                raise ValidationError(translate_customer_error(raw))

            if agent == "qa_approval":
                await self._ensure_qa_approval_gate(requirement_id=requirement_id)

    async def _ensure_qa_approval_gate(self, *, requirement_id: str) -> None:
        if await self.checker.has_approved_qa_approval(requirement_id):
            return
        raise ValidationError(translate_customer_error(ASSEMBLY_QA_GATE_MESSAGE))

