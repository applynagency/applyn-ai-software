from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.product_owner import ProductOwnerAgent
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.models.agent import AgentRunStatus, AgentType
from app.models.user import User
from app.repositories.agent import AgentOutputRepository, AgentRunRepository
from app.repositories.ai_agent import AIAgentRepository

logger = get_logger(__name__)

IMPLEMENTED_INTERNAL_AGENTS: tuple[str, ...] = (
    "product_owner",
    "business_analyst",
    "backend_architect",
    "backend_v1",
    "backend_v2",
    "backend_v3",
    "backend_code_review",
    "backend_execution",
    "uiux_designer",
    "frontend_architect",
    "frontend_v1",
    "frontend_v2",
    "frontend_v3",
    "frontend_code_review",
    "frontend_execution",
    "qa_architect",
    "unit_test_generator",
    "integration_test",
    "security_test",
    "performance_test",
    "qa_approval",
    "infrastructure_architect",
    "docker_agent",
    "cicd_agent",
    "kubernetes_agent",
    "observability_agent",
    "sre_approval_agent",
    "fullstack_assembly",
    "approval",
    "deployment",
)


@dataclass
class AgentDispatchResult:
    status: str
    output: dict[str, Any] | None = None
    tokens_used: int | None = None
    agent_run_id: str | None = None
    log_messages: list[str] | None = None
    error_message: str | None = None


class AgentDispatcher:
    """Dispatches internal and custom agents during workflow execution."""

    def is_implemented(self, internal_agent: str) -> bool:
        return internal_agent in IMPLEMENTED_INTERNAL_AGENTS

    async def dispatch_internal(
        self,
        *,
        internal_agent: str,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        if not self.is_implemented(internal_agent):
            return AgentDispatchResult(
                status="skipped",
                log_messages=[f"Agent '{internal_agent}' is not implemented yet — skipped"],
            )

        if internal_agent == "product_owner":
            return await self._dispatch_product_owner(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "business_analyst":
            return await self._dispatch_business_analyst(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "backend_architect":
            return await self._dispatch_backend_architect(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "backend_v1":
            return await self._dispatch_backend_v1(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "backend_v2":
            return await self._dispatch_backend_v2(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "backend_v3":
            return await self._dispatch_backend_v3(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "backend_code_review":
            return await self._dispatch_backend_code_review(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "backend_execution":
            return await self._dispatch_backend_execution(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "uiux_designer":
            return await self._dispatch_uiux_designer(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "frontend_architect":
            return await self._dispatch_frontend_architect(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "frontend_v1":
            return await self._dispatch_frontend_v1(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "frontend_v2":
            return await self._dispatch_frontend_v2(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "frontend_v3":
            return await self._dispatch_frontend_v3(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "frontend_code_review":
            return await self._dispatch_frontend_code_review(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "frontend_execution":
            return await self._dispatch_frontend_execution(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "qa_architect":
            return await self._dispatch_qa_architect(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "unit_test_generator":
            return await self._dispatch_unit_test_generator(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "integration_test":
            return await self._dispatch_integration_test(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "security_test":
            return await self._dispatch_security_test(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "performance_test":
            return await self._dispatch_performance_test(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "qa_approval":
            return await self._dispatch_qa_approval(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "infrastructure_architect":
            return await self._dispatch_infrastructure_architect(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "docker_agent":
            return await self._dispatch_docker_agent(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "cicd_agent":
            return await self._dispatch_cicd_agent(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "kubernetes_agent":
            return await self._dispatch_kubernetes_agent(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "observability_agent":
            return await self._dispatch_observability_agent(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "sre_approval_agent":
            return await self._dispatch_sre_approval_agent(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "fullstack_assembly":
            return await self._dispatch_fullstack_assembly(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "approval":
            return await self._dispatch_approval(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        if internal_agent == "deployment":
            return await self._dispatch_deployment(
                requirement_content=requirement_content,
                session=session,
                requirement_id=requirement_id,
                user=user,
            )

        return AgentDispatchResult(
            status="skipped",
            log_messages=[f"Agent '{internal_agent}' has no handler — skipped"],
        )

    async def dispatch_custom(
        self,
        *,
        custom_agent_id: str,
        prompt_template: str | None,
        requirement_content: str,
        session: AsyncSession,
    ) -> AgentDispatchResult:
        agent_repo = AIAgentRepository(session)
        agent = await agent_repo.get_with_details(custom_agent_id)
        if not agent:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Custom agent '{custom_agent_id}' not found",
            )

        prompt = prompt_template or agent.prompt_template or f"You are {agent.name}. {agent.goal or ''}"
        full_prompt = (
            f"{prompt.strip()}\n\n"
            f"Requirement to analyze:\n{requirement_content}\n\n"
            "Respond with a concise JSON object summarizing your analysis."
        )

        if not settings.ANTHROPIC_API_KEY:
            return AgentDispatchResult(
                status="completed",
                output={
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "mode": "stub",
                    "summary": f"Custom agent '{agent.name}' analyzed requirement (stub — no API key)",
                    "goal": agent.goal,
                },
                tokens_used=0,
                log_messages=[f"Custom agent '{agent.name}' executed in stub mode"],
            )

        try:
            from app.ai.gateway import AIGateway
            from app.ai.types import LLMMessage, LLMRequest

            req = LLMRequest(
                messages=[LLMMessage(role="user", content=full_prompt)],
                max_tokens=2048,
                feature="custom_agent",
                organization_id=getattr(agent, "organization_id", None),
            )
            response = await AIGateway(session).complete_pinned(req, provider="anthropic")
            text = response.text or ""
            tokens = response.usage.input_tokens + response.usage.output_tokens
            return AgentDispatchResult(
                status="completed",
                output={
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "mode": "llm",
                    "response": text,
                },
                tokens_used=tokens,
                log_messages=[f"Custom agent '{agent.name}' completed LLM execution"],
            )
        except Exception as exc:
            logger.error("custom_agent_failed", agent_id=custom_agent_id, error=str(exc))
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Custom agent '{agent.name}' failed: {exc}"],
            )

    async def _dispatch_via_execute_internal(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
        service_cls: type,
        label: str,
    ) -> AgentDispatchResult:
        """Generic dispatch for staged services exposing ``execute_internal``.

        Every staged agent (Business Analyst, the Architects, the Backend /
        Frontend V1/V2/V3 developers, UI/UX Designer, ...) is dispatched the same
        way: resolve the requirement's project + workspace for the org context,
        invoke ``service.execute_internal`` with the standard five arguments, and
        translate the outcome into an ``AgentDispatchResult``. This helper holds
        that flow once; the per-agent wrappers only supply the service class and
        the human-readable label used in log messages.
        """
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = service_cls(session)
        try:
            run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=run.tokens_used,
                agent_run_id=run.id,
                log_messages=[
                    f"{label} completed (validation score: {run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"{label} agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"{label} validation failed: {exc}"],
            )

    async def _dispatch_product_owner(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        run_repo = AgentRunRepository(session)
        output_repo = AgentOutputRepository(session)

        agent_run = await run_repo.create(
            agent_type=AgentType.PRODUCT_OWNER,
            status=AgentRunStatus.RUNNING,
            requirement_id=requirement_id,
            triggered_by=user.id,
            model_used=settings.ANTHROPIC_MODEL,
        )

        try:
            agent = ProductOwnerAgent()
            output, tokens_used = await agent.run(requirement_content)
            await output_repo.create(
                agent_run_id=agent_run.id,
                output_type="product_owner_analysis",
                content=output.model_dump(),
                version=1,
            )
            await run_repo.update(
                agent_run,
                status=AgentRunStatus.COMPLETED,
                tokens_used=tokens_used,
            )
            return AgentDispatchResult(
                status="completed",
                output=output.model_dump(),
                tokens_used=tokens_used,
                agent_run_id=agent_run.id,
                log_messages=["Product Owner agent completed analysis"],
            )
        except AgentError as exc:
            await run_repo.update(
                agent_run,
                status=AgentRunStatus.FAILED,
                error_message=str(exc),
            )
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                agent_run_id=agent_run.id,
                log_messages=[f"Product Owner agent failed: {exc}"],
            )

    async def _dispatch_business_analyst(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.business_analyst import BusinessAnalystService

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=BusinessAnalystService,
            label="Business Analyst",
        )

    async def _dispatch_backend_architect(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.backend_architect import BackendArchitectService

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=BackendArchitectService,
            label="Backend Architect",
        )

    async def _dispatch_backend_v1(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.backend_v1 import BackendDeveloperV1Service

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=BackendDeveloperV1Service,
            label="Backend Developer V1",
        )

    async def _dispatch_backend_v2(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.backend_v2 import BackendDeveloperV2Service

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=BackendDeveloperV2Service,
            label="Backend Developer V2",
        )

    async def _dispatch_backend_v3(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.backend_v3 import BackendDeveloperV3Service

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=BackendDeveloperV3Service,
            label="Backend Developer V3",
        )

    async def _dispatch_backend_code_review(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.backend_code_review import BackendCodeReviewService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = BackendCodeReviewService(session)
        try:
            review_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=review_run.tokens_used,
                agent_run_id=review_run.id,
                log_messages=[
                    "Backend Code Review completed "
                    f"(review score: {review_run.review_score}, "
                    f"approval: {review_run.approval_status})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Backend Code Review agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Backend Code Review validation failed: {exc}"],
            )

    async def _dispatch_backend_execution(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.backend_execution import BackendExecutionService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = BackendExecutionService(session)
        try:
            execution_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                agent_run_id=execution_run.id,
                log_messages=[
                    "Backend Execution completed "
                    f"(build: {execution_run.build_status}, "
                    f"approval: {execution_run.approval_status})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Backend Execution agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Backend Execution validation failed: {exc}"],
            )

    async def _dispatch_uiux_designer(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.uiux_designer import UIUXDesignerService

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=UIUXDesignerService,
            label="UI/UX Designer",
        )

    async def _dispatch_frontend_architect(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.frontend_architect import FrontendArchitectService

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=FrontendArchitectService,
            label="Frontend Architect",
        )

    async def _dispatch_frontend_v1(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.frontend_v1 import FrontendDeveloperV1Service

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=FrontendDeveloperV1Service,
            label="Frontend Developer V1",
        )

    async def _dispatch_frontend_v2(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.frontend_v2 import FrontendDeveloperV2Service

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=FrontendDeveloperV2Service,
            label="Frontend Developer V2",
        )

    async def _dispatch_frontend_v3(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.services.frontend_v3 import FrontendDeveloperV3Service

        return await self._dispatch_via_execute_internal(
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
            service_cls=FrontendDeveloperV3Service,
            label="Frontend Developer V3",
        )

    async def _dispatch_frontend_code_review(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.frontend_code_review import FrontendCodeReviewService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = FrontendCodeReviewService(session)
        try:
            review_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=review_run.tokens_used,
                agent_run_id=review_run.id,
                log_messages=[
                    "Frontend Code Review completed "
                    f"(review score: {review_run.review_score}, "
                    f"approval: {review_run.approval_status})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Frontend Code Review agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Frontend Code Review validation failed: {exc}"],
            )

    async def _dispatch_frontend_execution(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.frontend_execution import FrontendExecutionService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = FrontendExecutionService(session)
        try:
            execution_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                agent_run_id=execution_run.id,
                log_messages=[
                    "Frontend Execution completed "
                    f"(build: {execution_run.build_status}, "
                    f"approval: {execution_run.approval_status})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Frontend Execution agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Frontend Execution validation failed: {exc}"],
            )

    async def _dispatch_qa_architect(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.qa_architect import QAArchitectService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = QAArchitectService(session)
        try:
            qa_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=qa_run.tokens_used,
                agent_run_id=qa_run.id,
                log_messages=[
                    f"QA Architect completed (validation score: {qa_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"QA Architect agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"QA Architect validation failed: {exc}"],
            )

    async def _dispatch_unit_test_generator(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.unit_test_generator import UnitTestGeneratorService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = UnitTestGeneratorService(session)
        try:
            unit_test_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=unit_test_run.tokens_used,
                agent_run_id=unit_test_run.id,
                log_messages=[
                    "Unit Test Generator completed "
                    f"(validation score: {unit_test_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Unit Test Generator agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Unit Test Generator validation failed: {exc}"],
            )

    async def _dispatch_integration_test(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.integration_test import IntegrationTestService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = IntegrationTestService(session)
        try:
            integration_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=integration_run.tokens_used,
                agent_run_id=integration_run.id,
                log_messages=[
                    "Integration Test completed "
                    f"(validation score: {integration_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Integration Test agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Integration Test validation failed: {exc}"],
            )

    async def _dispatch_security_test(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.security_test import SecurityTestService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = SecurityTestService(session)
        try:
            security_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=security_run.tokens_used,
                agent_run_id=security_run.id,
                log_messages=[
                    "Security Test completed "
                    f"(validation score: {security_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Security Test agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Security Test validation failed: {exc}"],
            )

    async def _dispatch_performance_test(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.performance_test import PerformanceTestService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = PerformanceTestService(session)
        try:
            performance_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=performance_run.tokens_used,
                agent_run_id=performance_run.id,
                log_messages=[
                    "Performance Test completed "
                    f"(validation score: {performance_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Performance Test agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Performance Test validation failed: {exc}"],
            )

    async def _dispatch_qa_approval(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.qa_approval import QAApprovalService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = QAApprovalService(session)
        try:
            qa_approval_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=qa_approval_run.tokens_used,
                agent_run_id=qa_approval_run.id,
                log_messages=[
                    "QA Approval completed "
                    f"(validation score: {qa_approval_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"QA Approval agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"QA Approval validation failed: {exc}"],
            )

    async def _dispatch_infrastructure_architect(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.infrastructure_architect import InfrastructureArchitectService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = InfrastructureArchitectService(session)
        try:
            infra_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=infra_run.tokens_used,
                agent_run_id=infra_run.id,
                log_messages=[
                    f"Infrastructure Architect completed (validation score: {infra_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Infrastructure Architect agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Infrastructure Architect validation failed: {exc}"],
            )

    async def _dispatch_docker_agent(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.docker_agent import DockerAgentService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = DockerAgentService(session)
        try:
            docker_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=docker_run.tokens_used,
                agent_run_id=docker_run.id,
                log_messages=[
                    f"Docker Agent completed (validation score: {docker_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Docker Agent agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Docker Agent validation failed: {exc}"],
            )

    async def _dispatch_cicd_agent(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.cicd import CicdService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = CicdService(session)
        try:
            cicd_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=cicd_run.tokens_used,
                agent_run_id=cicd_run.id,
                log_messages=[f"CI/CD Agent completed (validation score: {cicd_run.validation_score})"],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"CI/CD Agent agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"CI/CD Agent validation failed: {exc}"],
            )

    async def _dispatch_kubernetes_agent(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.kubernetes import KubernetesService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = KubernetesService(session)
        try:
            k8s_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=k8s_run.tokens_used,
                agent_run_id=k8s_run.id,
                log_messages=[
                    f"Kubernetes Agent completed (validation score: {k8s_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Kubernetes Agent agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Kubernetes Agent validation failed: {exc}"],
            )

    async def _dispatch_observability_agent(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.observability import ObservabilityService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = ObservabilityService(session)
        try:
            obs_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=obs_run.tokens_used,
                agent_run_id=obs_run.id,
                log_messages=[
                    f"Observability Agent completed (validation score: {obs_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Observability Agent agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Observability Agent validation failed: {exc}"],
            )

    async def _dispatch_sre_approval_agent(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.sre_approval import SreApprovalService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = SreApprovalService(session)
        try:
            sre_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                tokens_used=sre_run.tokens_used,
                agent_run_id=sre_run.id,
                log_messages=[
                    f"SRE Approval completed (validation score: {sre_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"SRE Approval agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"SRE Approval validation failed: {exc}"],
            )

    async def _dispatch_fullstack_assembly(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.fullstack_assembly import FullStackAssemblyService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = FullStackAssemblyService(session)
        try:
            assembly_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                agent_run_id=assembly_run.id,
                log_messages=[
                    "Full Stack Assembly completed "
                    f"(status: {assembly_run.assembly_status}, "
                    f"score: {assembly_run.validation_score})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Full Stack Assembly agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Full Stack Assembly validation failed: {exc}"],
            )

    async def _dispatch_approval(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.approval import ApprovalWorkflowService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = ApprovalWorkflowService(session)
        try:
            approval_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                agent_run_id=approval_run.id,
                log_messages=[
                    "Approval Workflow completed "
                    f"(status: {approval_run.approval_status}, "
                    f"recommendation: {approval_run.recommendation})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Approval Workflow agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Approval Workflow validation failed: {exc}"],
            )

    async def _dispatch_deployment(
        self,
        *,
        requirement_content: str,
        session: AsyncSession,
        requirement_id: str,
        user: User,
    ) -> AgentDispatchResult:
        from app.core.exceptions import ValidationError as NexoraValidationError
        from app.repositories.project import ProjectRepository
        from app.repositories.requirement import RequirementRepository
        from app.repositories.workspace import WorkspaceRepository
        from app.services.deployment import DeploymentService

        requirement_repo = RequirementRepository(session)
        project_repo = ProjectRepository(session)
        workspace_repo = WorkspaceRepository(session)

        requirement = await requirement_repo.get_by_id(requirement_id)
        if not requirement:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Requirement '{requirement_id}' not found",
            )

        project = await project_repo.get_by_id(requirement.project_id)
        if not project:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Project '{requirement.project_id}' not found",
            )

        workspace = await workspace_repo.get_by_id(project.workspace_id)
        if not workspace:
            return AgentDispatchResult(
                status="failed",
                error_message=f"Workspace '{project.workspace_id}' not found",
            )

        service = DeploymentService(session)
        try:
            deployment_run, output = await service.execute_internal(
                organization_id=workspace.organization_id,
                project_id=project.id,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                user=user,
            )
            return AgentDispatchResult(
                status="completed",
                output=output,
                agent_run_id=deployment_run.id,
                log_messages=[
                    "Deployment completed "
                    f"(status: {deployment_run.status}, "
                    f"url: {deployment_run.live_url})"
                ],
            )
        except AgentError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Deployment agent failed: {exc}"],
            )
        except NexoraValidationError as exc:
            return AgentDispatchResult(
                status="failed",
                error_message=str(exc),
                log_messages=[f"Deployment validation failed: {exc}"],
            )
