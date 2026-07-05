"""Service layer for Custom AI Teams (Sprint 37A).

Configuration-only management of customer-defined AI Teams and the AI Agents
that belong to them. No execution happens here — Sprint 37B will layer
execution/collaboration/memory/orchestration on top of this stored config.

Strictly additive: this service never touches the internal APPYLN generation
pipeline, deployment providers, approval engine, or lifecycle engine.
"""

import json
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NexoraException
from app.core.logging import get_logger
from app.models.ai_team import (
    AITeam,
    AITeamAgent,
    AITeamAgentRunStatus,
    AITeamDocumentStatus,
    AITeamRunStatus,
    AITeamStatus,
)
from app.models.user import User
from app.repositories.ai_team import (
    AITeamAgentMemoryRepository,
    AITeamAgentRepository,
    AITeamAgentRunRepository,
    AITeamDocumentChunkRepository,
    AITeamDocumentRepository,
    AITeamRepository,
    AITeamRunRepository,
    AITeamRunStepRepository,
)
from app.repositories.audit import AuditLogRepository
from app.schemas.ai_team import (
    AITeamAgentCreate,
    AITeamAgentExecuteResponse,
    AITeamAgentListResponse,
    AITeamAgentMemoryCreate,
    AITeamAgentMemoryListResponse,
    AITeamAgentMemoryResponse,
    AITeamAgentMemoryUpdate,
    AITeamAgentResponse,
    AITeamAgentRunListResponse,
    AITeamAgentRunResponse,
    AITeamAgentUpdate,
    AITeamCreate,
    AITeamDocumentListResponse,
    AITeamDocumentResponse,
    AITeamExecuteResponse,
    AITeamExecuteStep,
    AITeamListResponse,
    AITeamResponse,
    AITeamRunListResponse,
    AITeamRunResponse,
    AITeamUpdate,
)
from app.services.ai_team_runner import (
    AITeamAgentRunner,
    build_collaboration_prompt,
    build_rag_prompt,
)
from app.services.document_processor import (
    DocumentProcessingError,
    chunk_text,
    extract_text,
    is_supported,
)
from app.services.embeddings import EmbeddingService, cosine_similarity
from app.tenancy.guards import (
    get_ai_team_agent_for_org,
    get_ai_team_for_org,
)
from app.tenancy.permissions import (
    can_manage_ai_teams,
    can_read_ai_teams,
    can_write_ai_teams,
)

logger = get_logger(__name__)

# Sprint 37C — preferred collaboration order. Agents are matched by keyword in
# their name or role; unmatched agents fall back to creation order (after these).
_ROLE_ORDER = ["CTO", "ARCHITECT", "BACKEND", "FRONTEND", "QA", "DEVOPS"]


def _agent_priority(agent: AITeamAgent) -> int:
    haystack = f"{agent.name} {agent.role}".upper()
    for index, token in enumerate(_ROLE_ORDER):
        if token in haystack:
            return index
    return len(_ROLE_ORDER)


async def retrieve_team_knowledge(
    chunk_repo: AITeamDocumentChunkRepository,
    team_id: str,
    organization_id: str,
    query: str,
) -> tuple[str, list[str]]:
    """Sprint 37D — embed the query, similarity-search the team's READY chunks,
    and return the concatenated top-K context plus the distinct source filenames.

    Shared by single-agent execution, team collaboration, and workflows.
    Returns ("", []) when the team has no indexed knowledge.
    """
    rows = await chunk_repo.list_ready_chunks_for_team(team_id, organization_id)
    if not rows:
        return "", []
    embedder = EmbeddingService()
    query_vec = await embedder.embed_query(query)
    scored: list[tuple[float, str, str]] = []
    for content, embedding_json, filename in rows:
        if not embedding_json:
            continue
        try:
            vec = json.loads(embedding_json)
        except (ValueError, TypeError):
            continue
        scored.append((cosine_similarity(query_vec, vec), content, filename))
    if not scored:
        return "", []
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: settings.KB_TOP_K]
    context_parts = [f"[{fname}]\n{content}" for _, content, fname in top]
    sources: list[str] = []
    for _, _, fname in top:
        if fname not in sources:
            sources.append(fname)
    return "\n\n---\n\n".join(context_parts), sources


async def retrieve_agent_memory(
    memory_repo: AITeamAgentMemoryRepository,
    agent_id: str,
    organization_id: str,
    query: str,
) -> tuple[str, list[str]]:
    """Sprint 39A — rank an agent's memories by semantic similarity to the query
    and return the concatenated top-K context plus the source memory titles.

    Importance (1–10) nudges the ranking but similarity stays dominant. Returns
    ("", []) when the agent has no memories. Shared by single-agent execution,
    team collaboration, and workflows.
    """
    memories = await memory_repo.list_all_for_agent(agent_id, organization_id)
    if not memories:
        return "", []
    embedder = EmbeddingService()
    query_vec = await embedder.embed_query(query)
    scored: list[tuple[float, object]] = []
    for mem in memories:
        if not mem.embedding:
            continue
        try:
            vec = json.loads(mem.embedding)
        except (ValueError, TypeError):
            continue
        sim = cosine_similarity(query_vec, vec)
        combined = sim + settings.MEMORY_IMPORTANCE_WEIGHT * (mem.importance_score or 0)
        scored.append((combined, mem))
    if not scored:
        return "", []
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [m for _, m in scored[: settings.MEMORY_TOP_K]]
    context_parts = [f"[{m.memory_type}] {m.title}\n{m.content}" for m in top]
    sources: list[str] = []
    for m in top:
        if m.title not in sources:
            sources.append(m.title)
    return "\n\n---\n\n".join(context_parts), sources


def memory_embedding_text(title: str, content: str) -> str:
    """Text embedded for a memory: title carries strong signal, repeated once."""
    return f"{(title or '').strip()}\n{(content or '').strip()}".strip()


class AITeamService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.team_repo = AITeamRepository(session)
        self.agent_repo = AITeamAgentRepository(session)
        self.run_repo = AITeamAgentRunRepository(session)
        self.team_run_repo = AITeamRunRepository(session)
        self.team_run_step_repo = AITeamRunStepRepository(session)
        self.doc_repo = AITeamDocumentRepository(session)
        self.chunk_repo = AITeamDocumentChunkRepository(session)
        self.memory_repo = AITeamAgentMemoryRepository(session)
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
    def _agent_to_response(self, agent: AITeamAgent) -> AITeamAgentResponse:
        return AITeamAgentResponse.model_validate(agent)

    def _team_to_response(self, team: AITeam) -> AITeamResponse:
        agents = sorted(team.agents or [], key=lambda item: item.created_at)
        return AITeamResponse(
            id=team.id,
            organization_id=team.organization_id,
            name=team.name,
            description=team.description,
            status=team.status,
            created_by=team.created_by,
            created_at=team.created_at,
            updated_at=team.updated_at,
            agent_count=len(agents),
            agents=[self._agent_to_response(agent) for agent in agents],
        )

    # ------------------------------------------------------------------- teams
    async def create_team(
        self, data: AITeamCreate, current_user: User, org_context: OrgContext
    ) -> AITeamResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        team = await self.team_repo.create(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            status=data.status,
            created_by=current_user.id,
        )
        team = await self.team_repo.get_with_agents(team.id)
        await self.audit_repo.log(
            action="ai_team_created",
            resource_type="ai_team",
            resource_id=team.id,
            user_id=current_user.id,
            details={"team_id": team.id, "name": team.name},
        )
        logger.info("ai_team_created", team_id=team.id)
        return self._team_to_response(team)

    async def list_teams(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        status: AITeamStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.team_repo.list_by_organization(
            organization_id, status=status, offset=offset, limit=limit
        )
        # Agents are eager-loaded by the repository; serialize directly (no N+1).
        detailed = [self._team_to_response(item) for item in items]
        return AITeamListResponse(items=detailed, total=total)

    async def get_team(
        self, team_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamResponse:
        team = await get_ai_team_for_org(self.session, team_id, org_context)
        self._ensure_read(current_user, org_context)
        return self._team_to_response(team)

    async def update_team(
        self, team_id: str, data: AITeamUpdate, current_user: User, org_context: OrgContext
    ) -> AITeamResponse:
        team = await get_ai_team_for_org(self.session, team_id, org_context)
        self._ensure_write(current_user, org_context)
        update_data = data.model_dump(exclude_none=True)
        updated = await self.team_repo.update(team, **update_data)
        team = await self.team_repo.get_with_agents(updated.id)
        await self.audit_repo.log(
            action="ai_team_updated",
            resource_type="ai_team",
            resource_id=team_id,
            user_id=current_user.id,
            details={
                "team_id": team_id,
                **{k: (v.value if isinstance(v, AITeamStatus) else v) for k, v in update_data.items()},
            },
        )
        return self._team_to_response(team)

    async def delete_team(
        self, team_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        team = await get_ai_team_for_org(self.session, team_id, org_context)
        self._ensure_manage(current_user, org_context)
        await self.team_repo.hard_delete(team)
        await self.audit_repo.log(
            action="ai_team_deleted",
            resource_type="ai_team",
            resource_id=team_id,
            user_id=current_user.id,
            details={"team_id": team_id},
        )

    # ------------------------------------------------------------------ agents
    async def create_agent(
        self, data: AITeamAgentCreate, current_user: User, org_context: OrgContext
    ) -> AITeamAgentResponse:
        # Resolving the parent team enforces existence + tenant isolation and
        # gives us the authoritative organization_id (ignoring any tampering).
        team = await get_ai_team_for_org(self.session, data.team_id, org_context)
        self._ensure_write(current_user, org_context)
        agent = await self.agent_repo.create(
            team_id=team.id,
            organization_id=team.organization_id,
            name=data.name,
            role=data.role,
            description=data.description,
            instructions=data.instructions,
            model=data.model,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            is_active=data.is_active,
        )
        await self.audit_repo.log(
            action="ai_agent_created",
            resource_type="ai_team_agent",
            resource_id=agent.id,
            user_id=current_user.id,
            details={"agent_id": agent.id, "team_id": team.id, "name": agent.name},
        )
        logger.info("ai_team_agent_created", agent_id=agent.id, team_id=team.id)
        return self._agent_to_response(agent)

    async def list_agents(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        team_id: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamAgentListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        if team_id:
            # Validates the team belongs to the caller's org before listing.
            await get_ai_team_for_org(self.session, team_id, org_context)
        items, total = await self.agent_repo.list_by_organization(
            organization_id,
            team_id=team_id,
            is_active=is_active,
            offset=offset,
            limit=limit,
        )
        return AITeamAgentListResponse(
            items=[self._agent_to_response(item) for item in items], total=total
        )

    async def get_agent(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamAgentResponse:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_read(current_user, org_context)
        return self._agent_to_response(agent)

    async def update_agent(
        self, agent_id: str, data: AITeamAgentUpdate, current_user: User, org_context: OrgContext
    ) -> AITeamAgentResponse:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        update_data = data.model_dump(exclude_none=True)
        updated = await self.agent_repo.update(agent, **update_data)
        await self.audit_repo.log(
            action="ai_agent_updated",
            resource_type="ai_team_agent",
            resource_id=agent_id,
            user_id=current_user.id,
            details={"agent_id": agent_id, "team_id": updated.team_id, **update_data},
        )
        return self._agent_to_response(updated)

    async def delete_agent(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_manage(current_user, org_context)
        team_id = agent.team_id
        await self.agent_repo.hard_delete(agent)
        await self.audit_repo.log(
            action="ai_agent_deleted",
            resource_type="ai_team_agent",
            resource_id=agent_id,
            user_id=current_user.id,
            details={"agent_id": agent_id, "team_id": team_id},
        )

    # --------------------------------------------------------------- execution
    def _run_to_response(self, run) -> AITeamAgentRunResponse:
        return AITeamAgentRunResponse.model_validate(run)

    async def execute_agent(
        self, agent_id: str, prompt: str, current_user: User, org_context: OrgContext
    ) -> AITeamAgentExecuteResponse:
        # Resolve + authorize the agent (tenant isolation, 404 on cross-org).
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)

        # Sprint 37D — ground the agent in the team's knowledge base (RAG).
        knowledge, knowledge_sources = await self._retrieve_knowledge(
            agent.team_id, agent.organization_id, prompt
        )
        # Sprint 39A — recall this agent's most relevant persistent memories.
        memory, memory_sources = await retrieve_agent_memory(
            self.memory_repo, agent.id, agent.organization_id, prompt
        )
        effective_prompt = build_rag_prompt(
            knowledge=knowledge, prompt=prompt, memory=memory
        )

        runner = AITeamAgentRunner(self.session)
        start = time.monotonic()
        try:
            response_text = await runner.run(
                instructions=agent.instructions,
                prompt=effective_prompt,
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                organization_id=agent.organization_id,
                user_id=getattr(current_user, "id", None),
            )
        except AgentError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            run = await self.run_repo.create(
                organization_id=agent.organization_id,
                agent_id=agent.id,
                prompt=prompt,
                response=None,
                status=AITeamAgentRunStatus.FAILED.value,
                execution_time_ms=elapsed_ms,
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="ai_agent_execution_failed",
                resource_type="ai_team_agent",
                resource_id=agent.id,
                user_id=current_user.id,
                details={"agent_id": agent.id, "team_id": agent.team_id, "run_id": run.id},
                status="failure",
            )
            # Persist the FAILED run + audit before raising; otherwise the
            # request-scoped session would roll them back on the exception.
            await self.session.commit()
            logger.info("ai_agent_execution_failed", agent_id=agent.id, run_id=run.id)
            # Customer-safe error; internal details are stored on the run, not leaked.
            raise NexoraException(
                "The AI agent could not complete the request. Please try again.",
                status_code=502,
            ) from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        run = await self.run_repo.create(
            organization_id=agent.organization_id,
            agent_id=agent.id,
            prompt=prompt,
            response=response_text,
            status=AITeamAgentRunStatus.COMPLETED.value,
            execution_time_ms=elapsed_ms,
        )
        await self.audit_repo.log(
            action="ai_agent_executed",
            resource_type="ai_team_agent",
            resource_id=agent.id,
            user_id=current_user.id,
            details={"agent_id": agent.id, "team_id": agent.team_id, "run_id": run.id},
        )
        if memory_sources:
            await self.audit_repo.log(
                action="ai_memory_used",
                resource_type="ai_team_agent",
                resource_id=agent.id,
                user_id=current_user.id,
                details={
                    "agent_id": agent.id,
                    "run_id": run.id,
                    "memory_sources": memory_sources,
                },
            )
        logger.info("ai_agent_executed", agent_id=agent.id, run_id=run.id, ms=elapsed_ms)
        # Sprint 62A: emit a first-class domain event for the activity feed and
        # any subscribed integrations. Best-effort (never breaks execution).
        from app.platform.events import DomainEventType, emit_event

        await emit_event(
            self.session, DomainEventType.AGENT_RUN_COMPLETED,
            organization_id=agent.organization_id,
            actor_id=getattr(current_user, "id", None),
            aggregate_type="ai_team_agent", aggregate_id=agent.id,
            payload={"summary": f"Agent '{agent.name}' completed a run",
                     "run_id": run.id}, source="ai_team")
        return AITeamAgentExecuteResponse(
            run_id=run.id,
            agent_id=agent.id,
            agent_name=agent.name,
            response=response_text,
            status=AITeamAgentRunStatus.COMPLETED.value,
            execution_time_ms=elapsed_ms,
            knowledge_sources=knowledge_sources,
            memory_sources=memory_sources,
        )

    async def list_agent_runs(
        self,
        agent_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamAgentRunListResponse:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.run_repo.list_for_agent(
            agent.id, agent.organization_id, offset=offset, limit=limit
        )
        return AITeamAgentRunListResponse(
            items=[self._run_to_response(item) for item in items], total=total
        )

    # ----------------------------------------------- multi-agent collaboration
    def _team_run_to_response(self, run) -> AITeamRunResponse:
        return AITeamRunResponse.model_validate(run)

    def _ordered_active_agents(self, team: AITeam) -> list[AITeamAgent]:
        active = [a for a in (team.agents or []) if a.is_active]
        # Stable sort: role priority first, then creation order for ties and
        # any agents whose role/name doesn't match a known collaboration role.
        return sorted(active, key=lambda a: (_agent_priority(a), a.created_at))

    async def execute_team(
        self, team_id: str, prompt: str, current_user: User, org_context: OrgContext
    ) -> AITeamExecuteResponse:
        """Orchestrate all active agents sequentially over a single prompt.

        Each agent receives the original prompt plus every prior agent's output.
        No autonomy, memory, chat, or continuous execution — one pass only.
        """
        team = await get_ai_team_for_org(self.session, team_id, org_context)
        self._ensure_write(current_user, org_context)

        agents = self._ordered_active_agents(team)
        if not agents:
            raise NexoraException(
                "This team has no active agents to execute. Add or enable an agent first.",
                status_code=400,
            )

        # Sprint 37D — retrieve knowledge once; every agent shares the same
        # grounding context for this task.
        knowledge, knowledge_sources = await self._retrieve_knowledge(
            team.id, team.organization_id, prompt
        )

        run = await self.team_run_repo.create(
            organization_id=team.organization_id,
            team_id=team.id,
            prompt=prompt,
            summary=None,
            status=AITeamRunStatus.RUNNING.value,
        )
        await self.audit_repo.log(
            action="ai_team_execution_started",
            resource_type="ai_team",
            resource_id=team.id,
            user_id=current_user.id,
            details={"team_id": team.id, "run_id": run.id, "agent_count": len(agents)},
        )

        runner = AITeamAgentRunner(self.session)
        prior_outputs: list[tuple[str, str]] = []
        steps_out: list[AITeamExecuteStep] = []
        memory_sources: list[str] = []
        total_start = time.monotonic()

        for index, agent in enumerate(agents, start=1):
            # Sprint 39A — each agent recalls its own persistent memories.
            agent_memory, agent_memory_sources = await retrieve_agent_memory(
                self.memory_repo, agent.id, agent.organization_id, prompt
            )
            for src in agent_memory_sources:
                if src not in memory_sources:
                    memory_sources.append(src)
            composed = build_collaboration_prompt(
                customer_prompt=prompt,
                prior_outputs=prior_outputs,
                instructions=agent.instructions,
                knowledge=knowledge,
                memory=agent_memory,
            )
            step_start = time.monotonic()
            try:
                response_text = await runner.run(
                    instructions=f"You are the {agent.name} ({agent.role}) on a collaborative AI team.",
                    prompt=composed,
                    model=agent.model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    organization_id=agent.organization_id,
                    user_id=getattr(current_user, "id", None),
                )
            except AgentError as exc:
                step_ms = int((time.monotonic() - step_start) * 1000)
                total_ms = int((time.monotonic() - total_start) * 1000)
                await self.team_run_step_repo.create(
                    run_id=run.id,
                    agent_id=agent.id,
                    agent_name=agent.name,
                    step_order=index,
                    prompt=composed,
                    response=None,
                    status=AITeamAgentRunStatus.FAILED.value,
                    execution_time_ms=step_ms,
                    error_message=str(exc),
                )
                await self.team_run_repo.update(
                    run,
                    status=AITeamRunStatus.FAILED.value,
                    execution_time_ms=total_ms,
                    error_message=f"Step {index} ({agent.name}) failed.",
                )
                await self.audit_repo.log(
                    action="ai_team_execution_failed",
                    resource_type="ai_team",
                    resource_id=team.id,
                    user_id=current_user.id,
                    details={
                        "team_id": team.id,
                        "run_id": run.id,
                        "failed_step": index,
                        "agent_id": agent.id,
                    },
                    status="failure",
                )
                # Persist failed step + run + audit before raising; the
                # request-scoped session would otherwise roll them back.
                await self.session.commit()
                logger.info(
                    "ai_team_execution_failed", team_id=team.id, run_id=run.id, step=index
                )
                raise NexoraException(
                    "The team collaboration could not be completed. Please try again.",
                    status_code=502,
                ) from exc

            step_ms = int((time.monotonic() - step_start) * 1000)
            await self.team_run_step_repo.create(
                run_id=run.id,
                agent_id=agent.id,
                agent_name=agent.name,
                step_order=index,
                prompt=composed,
                response=response_text,
                status=AITeamAgentRunStatus.COMPLETED.value,
                execution_time_ms=step_ms,
            )
            prior_outputs.append((agent.name, response_text))
            steps_out.append(AITeamExecuteStep(agent_name=agent.name, response=response_text))

        total_ms = int((time.monotonic() - total_start) * 1000)
        summary = (
            f"{team.name} completed a {len(steps_out)}-step collaboration for: "
            f"\"{prompt.strip()[:120]}\". "
            f"Final contribution by {steps_out[-1].agent_name}."
        )
        await self.team_run_repo.update(
            run,
            status=AITeamRunStatus.COMPLETED.value,
            execution_time_ms=total_ms,
            summary=summary,
        )
        await self.audit_repo.log(
            action="ai_team_execution_completed",
            resource_type="ai_team",
            resource_id=team.id,
            user_id=current_user.id,
            details={"team_id": team.id, "run_id": run.id, "steps": len(steps_out)},
        )
        if memory_sources:
            await self.audit_repo.log(
                action="ai_memory_used",
                resource_type="ai_team",
                resource_id=team.id,
                user_id=current_user.id,
                details={"team_id": team.id, "run_id": run.id, "memory_sources": memory_sources},
            )
        logger.info(
            "ai_team_execution_completed", team_id=team.id, run_id=run.id, ms=total_ms
        )
        return AITeamExecuteResponse(
            team_id=team.id,
            team_name=team.name,
            run_id=run.id,
            status=AITeamRunStatus.COMPLETED.value,
            execution_time_ms=total_ms,
            summary=summary,
            steps=steps_out,
            knowledge_sources=knowledge_sources,
            memory_sources=memory_sources,
        )

    async def list_team_runs(
        self,
        team_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamRunListResponse:
        team = await get_ai_team_for_org(self.session, team_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.team_run_repo.list_for_team(
            team.id, team.organization_id, offset=offset, limit=limit
        )
        return AITeamRunListResponse(
            items=[self._team_run_to_response(item) for item in items], total=total
        )

    async def get_team_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamRunResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        run = await self.team_run_repo.get_for_org(run_id, organization_id)
        if run is None:
            # Tenant isolation: cross-org or unknown run is indistinguishable.
            raise NexoraException("Team run not found.", status_code=404)
        return self._team_run_to_response(run)

    # ----------------------------------------------- knowledge base (RAG, 37D)
    def _document_to_response(self, doc) -> AITeamDocumentResponse:
        return AITeamDocumentResponse.model_validate(doc)

    async def _retrieve_knowledge(
        self, team_id: str, organization_id: str, query: str
    ) -> tuple[str, list[str]]:
        return await retrieve_team_knowledge(
            self.chunk_repo, team_id, organization_id, query
        )

    async def upload_document(
        self,
        team_id: str,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamDocumentResponse:
        team = await get_ai_team_for_org(self.session, team_id, org_context)
        self._ensure_write(current_user, org_context)

        if not filename or not is_supported(filename):
            raise NexoraException(
                "Unsupported file type. Upload a PDF, DOCX, TXT or Markdown file.",
                status_code=422,
            )
        if not data:
            raise NexoraException("The uploaded file is empty.", status_code=422)
        if len(data) > settings.KB_MAX_FILE_BYTES:
            raise NexoraException(
                "File is too large. The maximum size is "
                f"{settings.KB_MAX_FILE_BYTES // (1024 * 1024)} MB.",
                status_code=422,
            )

        document = await self.doc_repo.create(
            organization_id=team.organization_id,
            team_id=team.id,
            filename=filename,
            content_type=content_type or "application/octet-stream",
            file_size=len(data),
            status=AITeamDocumentStatus.PROCESSING.value,
            chunk_count=0,
        )
        await self.audit_repo.log(
            action="ai_document_uploaded",
            resource_type="ai_team_document",
            resource_id=document.id,
            user_id=current_user.id,
            details={"document_id": document.id, "team_id": team.id, "filename": filename},
        )

        try:
            text = extract_text(filename, data)
            chunks = chunk_text(text)
            if not chunks:
                raise DocumentProcessingError("No readable text found in the document.")
            embedder = EmbeddingService()
            embeddings = await embedder.embed_texts(chunks)
            for index, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=False)):
                await self.chunk_repo.create(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=json.dumps(vector),
                )
            await self.doc_repo.update(
                document,
                status=AITeamDocumentStatus.READY.value,
                chunk_count=len(chunks),
            )
            await self.audit_repo.log(
                action="ai_document_processed",
                resource_type="ai_team_document",
                resource_id=document.id,
                user_id=current_user.id,
                details={
                    "document_id": document.id,
                    "team_id": team.id,
                    "chunk_count": len(chunks),
                },
            )
            logger.info(
                "ai_document_processed", document_id=document.id, chunks=len(chunks)
            )
        except Exception as exc:  # noqa: BLE001 - mark FAILED, surface customer-safe state
            message = (
                str(exc)
                if isinstance(exc, DocumentProcessingError)
                else "The document could not be processed."
            )
            await self.doc_repo.update(
                document,
                status=AITeamDocumentStatus.FAILED.value,
                error_message=message,
            )
            await self.audit_repo.log(
                action="ai_document_processed",
                resource_type="ai_team_document",
                resource_id=document.id,
                user_id=current_user.id,
                details={"document_id": document.id, "team_id": team.id},
                status="failure",
            )
            # Persist the FAILED state; the request-scoped session would
            # otherwise roll it back if anything downstream raised.
            await self.session.commit()
            logger.info("ai_document_failed", document_id=document.id, error=message)

        refreshed = await self.doc_repo.get_for_org(document.id, team.organization_id)
        return self._document_to_response(refreshed or document)

    async def list_documents(
        self,
        team_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> AITeamDocumentListResponse:
        team = await get_ai_team_for_org(self.session, team_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.doc_repo.list_for_team(
            team.id, team.organization_id, offset=offset, limit=limit
        )
        return AITeamDocumentListResponse(
            items=[self._document_to_response(item) for item in items], total=total
        )

    async def delete_document(
        self, document_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        organization_id = org_context.requires_organization
        self._ensure_manage(current_user, org_context)
        document = await self.doc_repo.get_for_org(document_id, organization_id)
        if document is None:
            # Tenant isolation: cross-org or unknown document is indistinguishable.
            raise NexoraException("Document not found.", status_code=404)
        team_id = document.team_id
        await self.doc_repo.hard_delete(document)
        await self.audit_repo.log(
            action="ai_document_deleted",
            resource_type="ai_team_document",
            resource_id=document_id,
            user_id=current_user.id,
            details={"document_id": document_id, "team_id": team_id},
        )

    # ------------------------------------------------- agent memory (39A)
    def _memory_to_response(self, memory) -> AITeamAgentMemoryResponse:
        return AITeamAgentMemoryResponse.model_validate(memory)

    async def list_agent_memories(
        self,
        agent_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        memory_type: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> AITeamAgentMemoryListResponse:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.memory_repo.list_for_agent(
            agent.id,
            agent.organization_id,
            memory_type=memory_type,
            search=search,
            offset=offset,
            limit=limit,
        )
        return AITeamAgentMemoryListResponse(
            items=[self._memory_to_response(m) for m in items], total=total
        )

    async def create_agent_memory(
        self,
        agent_id: str,
        data: AITeamAgentMemoryCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamAgentMemoryResponse:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)

        # Embed title+content so the memory is retrievable by similarity later.
        embedder = EmbeddingService()
        vector = await embedder.embed_query(
            memory_embedding_text(data.title, data.content)
        )
        memory = await self.memory_repo.create(
            organization_id=agent.organization_id,
            agent_id=agent.id,
            memory_type=data.memory_type,
            title=data.title.strip(),
            content=data.content.strip(),
            importance_score=data.importance_score,
            created_from_run_id=data.created_from_run_id,
            embedding=json.dumps(vector),
        )
        await self.audit_repo.log(
            action="ai_memory_created",
            resource_type="ai_team_agent_memory",
            resource_id=memory.id,
            user_id=current_user.id,
            details={
                "memory_id": memory.id,
                "agent_id": agent.id,
                "memory_type": memory.memory_type,
            },
        )
        logger.info("ai_memory_created", memory_id=memory.id, agent_id=agent.id)
        return self._memory_to_response(memory)

    async def update_memory(
        self,
        memory_id: str,
        data: AITeamAgentMemoryUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamAgentMemoryResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        memory = await self.memory_repo.get_for_org(memory_id, organization_id)
        if memory is None:
            # Tenant isolation: cross-org or unknown memory is indistinguishable.
            raise NexoraException("Memory not found.", status_code=404)

        fields: dict = {}
        if data.memory_type is not None:
            fields["memory_type"] = data.memory_type
        if data.title is not None:
            fields["title"] = data.title.strip()
        if data.content is not None:
            fields["content"] = data.content.strip()
        if data.importance_score is not None:
            fields["importance_score"] = data.importance_score

        # Re-embed when the searchable text changed.
        if "title" in fields or "content" in fields:
            embedder = EmbeddingService()
            new_title = fields.get("title", memory.title)
            new_content = fields.get("content", memory.content)
            vector = await embedder.embed_query(
                memory_embedding_text(new_title, new_content)
            )
            fields["embedding"] = json.dumps(vector)

        if fields:
            memory = await self.memory_repo.update(memory, **fields)
        await self.audit_repo.log(
            action="ai_memory_updated",
            resource_type="ai_team_agent_memory",
            resource_id=memory.id,
            user_id=current_user.id,
            details={"memory_id": memory.id, "agent_id": memory.agent_id},
        )
        return self._memory_to_response(memory)

    async def delete_memory(
        self, memory_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        memory = await self.memory_repo.get_for_org(memory_id, organization_id)
        if memory is None:
            raise NexoraException("Memory not found.", status_code=404)
        agent_id = memory.agent_id
        await self.memory_repo.hard_delete(memory)
        await self.audit_repo.log(
            action="ai_memory_deleted",
            resource_type="ai_team_agent_memory",
            resource_id=memory_id,
            user_id=current_user.id,
            details={"memory_id": memory_id, "agent_id": agent_id},
        )
