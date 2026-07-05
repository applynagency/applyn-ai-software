"""Sprint 38A — Reusable Team Workflows.

A workflow is a saved, ordered template over an existing AI Team: which team
runs, in what agent order, with optional per-step instruction overrides and an
optional default prompt. Execution reuses the Sprint 37C collaboration engine
(sequential context propagation) and the Sprint 37D knowledge base.

Strictly additive and template-only: no scheduling, autonomous execution,
memory, or approval gates. Existing 37A–37D behavior is untouched.
"""

import json
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import AgentError, ForbiddenError, NexoraException
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.ai_team import (
    AITeamAgent,
    AITeamWorkflowApprovalStatus,
    AITeamWorkflowRunStatus,
)
from app.models.user import User
from app.repositories.ai_team import (
    AITeamAgentMemoryRepository,
    AITeamAgentRepository,
    AITeamDocumentChunkRepository,
    AITeamRepository,
    AITeamWorkflowApprovalRepository,
    AITeamWorkflowRepository,
    AITeamWorkflowRunRepository,
    AITeamWorkflowStepRepository,
)
from app.repositories.audit import AuditLogRepository
from app.schemas.ai_team import (
    AITeamExecuteStep,
    AITeamWorkflowApprovalListResponse,
    AITeamWorkflowApprovalResponse,
    AITeamWorkflowCreate,
    AITeamWorkflowExecuteResponse,
    AITeamWorkflowListResponse,
    AITeamWorkflowResponse,
    AITeamWorkflowRunListResponse,
    AITeamWorkflowRunResponse,
    AITeamWorkflowStepInput,
    AITeamWorkflowStepResponse,
    AITeamWorkflowUpdate,
)
from app.services.ai_team import retrieve_agent_memory, retrieve_team_knowledge
from app.services.ai_team_runner import AITeamAgentRunner, build_collaboration_prompt
from app.tenancy.guards import get_ai_team_for_org
from app.tenancy.permissions import (
    can_manage_ai_teams,
    can_read_ai_teams,
    can_write_ai_teams,
)

logger = get_logger(__name__)


class AITeamWorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow_repo = AITeamWorkflowRepository(session)
        self.step_repo = AITeamWorkflowStepRepository(session)
        self.run_repo = AITeamWorkflowRunRepository(session)
        self.team_repo = AITeamRepository(session)
        self.agent_repo = AITeamAgentRepository(session)
        self.chunk_repo = AITeamDocumentChunkRepository(session)
        self.memory_repo = AITeamAgentMemoryRepository(session)
        self.approval_repo = AITeamWorkflowApprovalRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ------------------------------------------------------------------ guards
    def _ensure_read(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_manage(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_manage_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # --------------------------------------------------------------- responses
    def _step_to_response(
        self, step, agent_map: dict[str, AITeamAgent]
    ) -> AITeamWorkflowStepResponse:
        agent = agent_map.get(step.agent_id) if step.agent_id else None
        return AITeamWorkflowStepResponse(
            id=step.id,
            agent_id=step.agent_id,
            agent_name=agent.name if agent else "(removed agent)",
            role=agent.role if agent else None,
            is_active=agent.is_active if agent else False,
            step_order=step.step_order,
            custom_instructions=step.custom_instructions,
            requires_approval=step.requires_approval,
            approval_name=step.approval_name,
            approver_role=step.approver_role,
            created_at=step.created_at,
        )

    def _workflow_to_response(
        self, workflow, agent_map: dict[str, AITeamAgent], team_name: str | None
    ) -> AITeamWorkflowResponse:
        steps = sorted(workflow.steps or [], key=lambda s: s.step_order)
        return AITeamWorkflowResponse(
            id=workflow.id,
            organization_id=workflow.organization_id,
            team_id=workflow.team_id,
            team_name=team_name,
            name=workflow.name,
            description=workflow.description,
            default_prompt=workflow.default_prompt,
            is_active=workflow.is_active,
            step_count=len(steps),
            steps=[self._step_to_response(s, agent_map) for s in steps],
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

    async def _team_agent_map(
        self, team_id: str, organization_id: str
    ) -> dict[str, AITeamAgent]:
        agents, _ = await self.agent_repo.list_by_organization(
            organization_id, team_id=team_id, offset=0, limit=500
        )
        return {a.id: a for a in agents}

    def _validate_steps(
        self,
        steps: list[AITeamWorkflowStepInput],
        agent_map: dict[str, AITeamAgent],
    ) -> None:
        for step in steps:
            if step.agent_id not in agent_map:
                raise NexoraException(
                    "One or more workflow steps reference an agent that does not "
                    "belong to this team.",
                    status_code=422,
                )

    async def _create_steps(
        self, workflow_id: str, steps: list[AITeamWorkflowStepInput]
    ) -> None:
        for index, step in enumerate(steps, start=1):
            await self.step_repo.create(
                workflow_id=workflow_id,
                agent_id=step.agent_id,
                step_order=step.step_order or index,
                custom_instructions=step.custom_instructions,
                requires_approval=step.requires_approval,
                approval_name=step.approval_name,
                approver_role=step.approver_role,
            )

    # --------------------------------------------------------------- workflows
    async def create_workflow(
        self, data: AITeamWorkflowCreate, current_user: User, org_context: OrgContext
    ) -> AITeamWorkflowResponse:
        team = await get_ai_team_for_org(self.session, data.team_id, org_context)
        self._ensure_write(current_user, org_context)

        agent_map = await self._team_agent_map(team.id, team.organization_id)
        self._validate_steps(data.steps, agent_map)

        workflow = await self.workflow_repo.create(
            organization_id=team.organization_id,
            team_id=team.id,
            name=data.name,
            description=data.description,
            default_prompt=data.default_prompt,
            is_active=data.is_active,
        )
        await self._create_steps(workflow.id, data.steps)
        workflow = await self.workflow_repo.get_with_steps(workflow.id)
        await self.audit_repo.log(
            action="workflow_created",
            resource_type="ai_team_workflow",
            resource_id=workflow.id,
            user_id=current_user.id,
            details={"workflow_id": workflow.id, "team_id": team.id, "name": workflow.name},
        )
        logger.info("ai_team_workflow_created", workflow_id=workflow.id, team_id=team.id)
        return self._workflow_to_response(workflow, agent_map, team.name)

    async def list_workflows(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        team_id: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamWorkflowListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.workflow_repo.list_by_organization(
            organization_id,
            team_id=team_id,
            is_active=is_active,
            offset=offset,
            limit=limit,
        )
        # Build org-wide team/agent maps once for response enrichment.
        teams, _ = await self.team_repo.list_by_organization(
            organization_id, offset=0, limit=500
        )
        team_names = {t.id: t.name for t in teams}
        all_agents, _ = await self.agent_repo.list_by_organization(
            organization_id, offset=0, limit=1000
        )
        agent_map = {a.id: a for a in all_agents}
        return AITeamWorkflowListResponse(
            items=[
                self._workflow_to_response(w, agent_map, team_names.get(w.team_id))
                for w in items
            ],
            total=total,
        )

    async def get_workflow(
        self, workflow_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamWorkflowResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        workflow = await self.workflow_repo.get_for_org(workflow_id, organization_id)
        if workflow is None:
            raise NexoraException("Workflow not found.", status_code=404)
        agent_map = await self._team_agent_map(workflow.team_id, organization_id)
        team = await self.team_repo.get_by_id(workflow.team_id)
        return self._workflow_to_response(
            workflow, agent_map, team.name if team else None
        )

    async def update_workflow(
        self,
        workflow_id: str,
        data: AITeamWorkflowUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamWorkflowResponse:
        organization_id = org_context.requires_organization
        workflow = await self.workflow_repo.get_for_org(workflow_id, organization_id)
        if workflow is None:
            raise NexoraException("Workflow not found.", status_code=404)
        self._ensure_write(current_user, org_context)

        agent_map = await self._team_agent_map(workflow.team_id, organization_id)
        scalar = data.model_dump(exclude_none=True, exclude={"steps"})
        if scalar:
            await self.workflow_repo.update(workflow, **scalar)
        if data.steps is not None:
            self._validate_steps(data.steps, agent_map)
            for existing in list(workflow.steps or []):
                await self.step_repo.hard_delete(existing)
            await self._create_steps(workflow.id, data.steps)

        workflow = await self.workflow_repo.get_with_steps(workflow.id)
        await self.audit_repo.log(
            action="workflow_updated",
            resource_type="ai_team_workflow",
            resource_id=workflow.id,
            user_id=current_user.id,
            details={"workflow_id": workflow.id, "team_id": workflow.team_id},
        )
        team = await self.team_repo.get_by_id(workflow.team_id)
        return self._workflow_to_response(
            workflow, agent_map, team.name if team else None
        )

    async def delete_workflow(
        self, workflow_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        organization_id = org_context.requires_organization
        workflow = await self.workflow_repo.get_for_org(workflow_id, organization_id)
        if workflow is None:
            raise NexoraException("Workflow not found.", status_code=404)
        self._ensure_manage(current_user, org_context)
        team_id = workflow.team_id
        await self.workflow_repo.hard_delete(workflow)
        await self.audit_repo.log(
            action="workflow_deleted",
            resource_type="ai_team_workflow",
            resource_id=workflow_id,
            user_id=current_user.id,
            details={"workflow_id": workflow_id, "team_id": team_id},
        )

    # --------------------------------------------------------------- execution
    def _run_to_response(self, run) -> AITeamWorkflowRunResponse:
        return AITeamWorkflowRunResponse.model_validate(run)

    async def execute_workflow(
        self,
        workflow_id: str,
        prompt: str | None,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamWorkflowExecuteResponse:
        organization_id = org_context.requires_organization
        workflow = await self.workflow_repo.get_for_org(workflow_id, organization_id)
        if workflow is None:
            raise NexoraException("Workflow not found.", status_code=404)
        self._ensure_write(current_user, org_context)

        effective_prompt = (prompt or "").strip() or (workflow.default_prompt or "").strip()
        if not effective_prompt:
            raise NexoraException(
                "Provide a prompt or set a default prompt on the workflow.",
                status_code=400,
            )
        return await self.run_workflow_core(
            workflow,
            effective_prompt,
            organization_id,
            execution_source="MANUAL",
            actor_user_id=current_user.id,
        )

    async def run_workflow_core(
        self,
        workflow,
        effective_prompt: str,
        organization_id: str,
        *,
        execution_source: str = "MANUAL",
        actor_user_id: str | None = None,
    ) -> AITeamWorkflowExecuteResponse:
        """Start a workflow run, executing until completion or an approval gate.

        Shared by manual, run-now, and scheduled runs. Sprint 38C makes this
        pausable: it snapshots the execution plan onto the run so an
        approval-paused run can later resume (see ``_continue_run``).
        """
        agent_map = await self._team_agent_map(workflow.team_id, organization_id)
        # Snapshot the ordered, executable plan now so a later workflow edit
        # cannot corrupt an in-flight (possibly paused) run.
        ordered = sorted(workflow.steps or [], key=lambda s: s.step_order)
        plan: list[dict] = []
        for step in ordered:
            agent = agent_map.get(step.agent_id) if step.agent_id else None
            if not (agent and agent.is_active):
                continue
            instructions = (step.custom_instructions or "").strip() or agent.instructions
            plan.append(
                {
                    "step_order": step.step_order,
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "role": agent.role,
                    "instructions": instructions,
                    "model": agent.model,
                    "temperature": agent.temperature,
                    "max_tokens": agent.max_tokens,
                    "requires_approval": bool(step.requires_approval),
                    "approval_name": step.approval_name,
                    "approver_role": step.approver_role,
                }
            )
        if not plan:
            raise NexoraException(
                "This workflow has no active agents to execute.", status_code=400
            )

        run = await self.run_repo.create(
            organization_id=organization_id,
            workflow_id=workflow.id,
            prompt=effective_prompt,
            summary=None,
            status=AITeamWorkflowRunStatus.RUNNING.value,
            execution_source=execution_source,
            plan=json.dumps(plan),
            completed_steps=json.dumps([]),
            resume_index=0,
            execution_time_ms=0,
        )
        return await self._continue_run(run, workflow, actor_user_id=actor_user_id)

    async def _continue_run(
        self, run, workflow, *, actor_user_id: str | None = None
    ) -> AITeamWorkflowExecuteResponse:
        """Execute plan steps from ``run.resume_index`` until done or paused.

        On an approval-gated step the run is persisted as WAITING_FOR_APPROVAL,
        a PENDING approval record is created, and execution stops; the same loop
        resumes later from the stored ``resume_index`` and ``completed_steps``.
        """
        plan: list[dict] = json.loads(run.plan or "[]")
        completed: list[dict] = json.loads(run.completed_steps or "[]")
        start_index = run.resume_index or 0
        organization_id = run.organization_id
        execution_source = run.execution_source

        # Re-establish prior context (deterministic across pause/resume).
        knowledge, knowledge_sources = await retrieve_team_knowledge(
            self.chunk_repo, workflow.team_id, organization_id, run.prompt
        )
        prior_outputs: list[tuple[str, str]] = [
            (c["agent_name"], c["response"]) for c in completed
        ]
        steps_out: list[AITeamExecuteStep] = [
            AITeamExecuteStep(agent_name=c["agent_name"], response=c["response"])
            for c in completed
        ]

        runner = AITeamAgentRunner(self.session)
        base_ms = run.execution_time_ms or 0
        segment_start = time.monotonic()
        memory_sources: list[str] = []

        for index in range(start_index, len(plan)):
            step = plan[index]
            # Sprint 39A — each step's agent recalls its own persistent memories.
            agent_memory, agent_memory_sources = ("", [])
            if step.get("agent_id"):
                agent_memory, agent_memory_sources = await retrieve_agent_memory(
                    self.memory_repo, step["agent_id"], organization_id, run.prompt
                )
                for src in agent_memory_sources:
                    if src not in memory_sources:
                        memory_sources.append(src)
            composed = build_collaboration_prompt(
                customer_prompt=run.prompt,
                prior_outputs=prior_outputs,
                instructions=step["instructions"],
                knowledge=knowledge,
                memory=agent_memory,
            )
            try:
                response_text = await runner.run(
                    instructions=f"You are the {step['agent_name']} ({step['role']}) on a collaborative AI team.",
                    prompt=composed,
                    model=step["model"],
                    temperature=step["temperature"],
                    max_tokens=step["max_tokens"],
                    organization_id=organization_id,
                )
            except AgentError as exc:
                total_ms = base_ms + int((time.monotonic() - segment_start) * 1000)
                await self.run_repo.update(
                    run,
                    status=AITeamWorkflowRunStatus.FAILED.value,
                    execution_time_ms=total_ms,
                    error_message=f"Step {index + 1} ({step['agent_name']}) failed.",
                )
                await self.audit_repo.log(
                    action="workflow_execution_failed",
                    resource_type="ai_team_workflow",
                    resource_id=workflow.id,
                    user_id=actor_user_id,
                    details={
                        "workflow_id": workflow.id,
                        "run_id": run.id,
                        "failed_step": index + 1,
                        "agent_id": step["agent_id"],
                        "execution_source": execution_source,
                    },
                    status="failure",
                )
                await self.session.commit()
                logger.info(
                    "ai_team_workflow_failed", workflow_id=workflow.id, run_id=run.id, step=index + 1
                )
                raise NexoraException(
                    "The workflow could not be completed. Please try again.",
                    status_code=502,
                ) from exc

            prior_outputs.append((step["agent_name"], response_text))
            completed.append({"agent_name": step["agent_name"], "response": response_text})
            steps_out.append(
                AITeamExecuteStep(agent_name=step["agent_name"], response=response_text)
            )

            # Sprint 38C — pause for human review after this step's output.
            if step["requires_approval"]:
                total_ms = base_ms + int((time.monotonic() - segment_start) * 1000)
                approval_name = step.get("approval_name") or f"{step['agent_name']} approval"
                await self.run_repo.update(
                    run,
                    status=AITeamWorkflowRunStatus.WAITING_FOR_APPROVAL.value,
                    execution_time_ms=total_ms,
                    completed_steps=json.dumps(completed),
                    resume_index=index + 1,
                    summary=f"Paused for approval: {approval_name}.",
                )
                await self.approval_repo.create(
                    organization_id=organization_id,
                    workflow_id=workflow.id,
                    workflow_run_id=run.id,
                    step_order=step["step_order"],
                    approval_name=approval_name,
                    approval_description=(
                        f"Review the output of {step['agent_name']} before the workflow continues."
                    ),
                    approver_role=step.get("approver_role"),
                    status=AITeamWorkflowApprovalStatus.PENDING.value,
                )
                await self.audit_repo.log(
                    action="workflow_approval_created",
                    resource_type="ai_team_workflow",
                    resource_id=workflow.id,
                    user_id=actor_user_id,
                    details={
                        "workflow_id": workflow.id,
                        "run_id": run.id,
                        "step_order": step["step_order"],
                        "approval_name": approval_name,
                    },
                )
                await self.session.commit()
                logger.info(
                    "ai_team_workflow_paused",
                    workflow_id=workflow.id,
                    run_id=run.id,
                    step=index + 1,
                )
                return AITeamWorkflowExecuteResponse(
                    workflow_id=workflow.id,
                    workflow_name=workflow.name,
                    run_id=run.id,
                    status=AITeamWorkflowRunStatus.WAITING_FOR_APPROVAL.value,
                    execution_source=execution_source,
                    execution_time_ms=total_ms,
                    summary=f"Paused for approval: {approval_name}.",
                    steps=steps_out,
                    knowledge_sources=knowledge_sources,
                    memory_sources=memory_sources,
                )

        total_ms = base_ms + int((time.monotonic() - segment_start) * 1000)
        summary = (
            f"Workflow \"{workflow.name}\" completed a {len(steps_out)}-step run for: "
            f"\"{run.prompt[:120]}\". "
            f"Final contribution by {steps_out[-1].agent_name}."
        )
        await self.run_repo.update(
            run,
            status=AITeamWorkflowRunStatus.COMPLETED.value,
            execution_time_ms=total_ms,
            completed_steps=json.dumps(completed),
            resume_index=len(plan),
            summary=summary,
        )
        await self.audit_repo.log(
            action="workflow_executed",
            resource_type="ai_team_workflow",
            resource_id=workflow.id,
            user_id=actor_user_id,
            details={
                "workflow_id": workflow.id,
                "run_id": run.id,
                "steps": len(steps_out),
                "execution_source": execution_source,
            },
        )
        if memory_sources:
            await self.audit_repo.log(
                action="ai_memory_used",
                resource_type="ai_team_workflow",
                resource_id=workflow.id,
                user_id=actor_user_id,
                details={
                    "workflow_id": workflow.id,
                    "run_id": run.id,
                    "memory_sources": memory_sources,
                },
            )
        logger.info(
            "ai_team_workflow_executed",
            workflow_id=workflow.id,
            run_id=run.id,
            ms=total_ms,
            source=execution_source,
        )
        return AITeamWorkflowExecuteResponse(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            run_id=run.id,
            status=AITeamWorkflowRunStatus.COMPLETED.value,
            execution_source=execution_source,
            execution_time_ms=total_ms,
            summary=summary,
            steps=steps_out,
            knowledge_sources=knowledge_sources,
            memory_sources=memory_sources,
        )

    async def list_workflow_runs(
        self,
        workflow_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamWorkflowRunListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        workflow = await self.workflow_repo.get_for_org(workflow_id, organization_id)
        if workflow is None:
            raise NexoraException("Workflow not found.", status_code=404)
        items, total = await self.run_repo.list_for_workflow(
            workflow.id, organization_id, offset=offset, limit=limit
        )
        return AITeamWorkflowRunListResponse(
            items=[self._run_to_response(item) for item in items], total=total
        )

    # ----------------------------------------------------- approvals (38C)
    async def list_approvals(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        workflow_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> AITeamWorkflowApprovalListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.approval_repo.list_by_organization(
            organization_id, workflow_id=workflow_id, status=status, offset=offset, limit=limit
        )
        return AITeamWorkflowApprovalListResponse(
            items=[AITeamWorkflowApprovalResponse.model_validate(a) for a in items],
            total=total,
        )

    async def get_approval(
        self, approval_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamWorkflowApprovalResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        approval = await self.approval_repo.get_for_org(approval_id, organization_id)
        if approval is None:
            raise NexoraException("Approval not found.", status_code=404)
        return AITeamWorkflowApprovalResponse.model_validate(approval)

    async def list_run_approvals(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamWorkflowApprovalListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        run = await self.run_repo.get_for_org(run_id, organization_id)
        if run is None:
            raise NexoraException("Workflow run not found.", status_code=404)
        items = await self.approval_repo.list_for_run(run_id, organization_id)
        return AITeamWorkflowApprovalListResponse(
            items=[AITeamWorkflowApprovalResponse.model_validate(a) for a in items],
            total=len(items),
        )

    async def approve(
        self,
        approval_id: str,
        comments: str | None,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamWorkflowExecuteResponse:
        organization_id = org_context.requires_organization
        approval = await self.approval_repo.get_for_org(approval_id, organization_id)
        if approval is None:
            raise NexoraException("Approval not found.", status_code=404)
        self._ensure_write(current_user, org_context)
        if approval.status != AITeamWorkflowApprovalStatus.PENDING.value:
            raise NexoraException("This approval has already been decided.", status_code=409)

        run = await self.run_repo.get_for_org(approval.workflow_run_id, organization_id)
        workflow = await self.workflow_repo.get_for_org(approval.workflow_id, organization_id)
        if run is None or workflow is None:
            raise NexoraException("Workflow run not found.", status_code=404)

        await self.approval_repo.update(
            approval,
            status=AITeamWorkflowApprovalStatus.APPROVED.value,
            approved_by=current_user.id,
            approved_at=utcnow(),
            comments=comments,
        )
        await self.audit_repo.log(
            action="workflow_approved",
            resource_type="ai_team_workflow",
            resource_id=workflow.id,
            user_id=current_user.id,
            details={"workflow_id": workflow.id, "run_id": run.id, "approval_id": approval.id},
        )
        await self.audit_repo.log(
            action="workflow_resumed",
            resource_type="ai_team_workflow",
            resource_id=workflow.id,
            user_id=current_user.id,
            details={"workflow_id": workflow.id, "run_id": run.id, "approval_id": approval.id},
        )
        await self.run_repo.update(run, status=AITeamWorkflowRunStatus.RUNNING.value)
        # Resume from the stored plan/index; may complete or hit another gate.
        return await self._continue_run(run, workflow, actor_user_id=current_user.id)

    async def reject(
        self,
        approval_id: str,
        comments: str | None,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamWorkflowApprovalResponse:
        organization_id = org_context.requires_organization
        approval = await self.approval_repo.get_for_org(approval_id, organization_id)
        if approval is None:
            raise NexoraException("Approval not found.", status_code=404)
        self._ensure_write(current_user, org_context)
        if approval.status != AITeamWorkflowApprovalStatus.PENDING.value:
            raise NexoraException("This approval has already been decided.", status_code=409)

        run = await self.run_repo.get_for_org(approval.workflow_run_id, organization_id)
        await self.approval_repo.update(
            approval,
            status=AITeamWorkflowApprovalStatus.REJECTED.value,
            approved_by=current_user.id,
            approved_at=utcnow(),
            comments=comments,
        )
        if run is not None:
            reason = (comments or "").strip() or "Rejected by approver."
            await self.run_repo.update(
                run,
                status=AITeamWorkflowRunStatus.FAILED.value,
                error_message=f"Rejected at approval '{approval.approval_name}': {reason}",
            )
        await self.audit_repo.log(
            action="workflow_rejected",
            resource_type="ai_team_workflow",
            resource_id=approval.workflow_id,
            user_id=current_user.id,
            details={
                "workflow_id": approval.workflow_id,
                "run_id": approval.workflow_run_id,
                "approval_id": approval.id,
            },
            status="failure",
        )
        await self.session.commit()
        return AITeamWorkflowApprovalResponse.model_validate(approval)
