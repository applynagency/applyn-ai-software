"""Repositories for Custom AI Teams (Sprint 37A)."""

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_team import (
    AITeam,
    AITeamAgent,
    AITeamAgentMemory,
    AITeamAgentRun,
    AITeamAgentTool,
    AITeamDocument,
    AITeamDocumentChunk,
    AITeamDocumentStatus,
    AITeamRun,
    AITeamRunStep,
    AITeamStatus,
    AITeamTool,
    AITeamToolCredential,
    AITeamToolRun,
    AITeamWorkflow,
    AITeamWorkflowApproval,
    AITeamWorkflowRun,
    AITeamWorkflowSchedule,
    AITeamWorkflowStep,
)
from app.repositories.base import BaseRepository


class AITeamRepository(BaseRepository[AITeam]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeam, session)

    async def get_with_agents(self, team_id: str) -> AITeam | None:
        stmt = (
            select(AITeam)
            .where(AITeam.id == team_id)
            .options(selectinload(AITeam.agents))
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        status: AITeamStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AITeam], int]:
        filters = [AITeam.organization_id == organization_id]
        if status:
            filters.append(AITeam.status == status)
        # Eager-load agents so the caller can serialize the whole page without a
        # per-team follow-up query (AITeam.agents is selectin, batched to one IN).
        return await self.list_all(
            filters=filters,
            offset=offset,
            limit=limit,
            options=[selectinload(AITeam.agents)],
        )

    async def get_default_for_org(self, organization_id: str) -> AITeam | None:
        """Sprint 54B.1 — the org's default team (with agents), if any."""
        stmt = (
            select(AITeam)
            .where(
                AITeam.organization_id == organization_id,
                AITeam.is_default.is_(True),
            )
            .options(selectinload(AITeam.agents))
            .order_by(AITeam.created_at.asc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class AITeamAgentRepository(BaseRepository[AITeamAgent]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamAgent, session)

    async def get_for_org(self, agent_id: str, organization_id: str) -> AITeamAgent | None:
        stmt = select(AITeamAgent).where(
            AITeamAgent.id == agent_id,
            AITeamAgent.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        team_id: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AITeamAgent], int]:
        filters = [AITeamAgent.organization_id == organization_id]
        if team_id:
            filters.append(AITeamAgent.team_id == team_id)
        if is_active is not None:
            filters.append(AITeamAgent.is_active == is_active)
        return await self.list_all(filters=filters, offset=offset, limit=limit)


class AITeamAgentRunRepository(BaseRepository[AITeamAgentRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamAgentRun, session)

    async def get_for_org(self, run_id: str, organization_id: str) -> AITeamAgentRun | None:
        stmt = select(AITeamAgentRun).where(
            AITeamAgentRun.id == run_id,
            AITeamAgentRun.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_agent(
        self, agent_id: str, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AITeamAgentRun], int]:
        filters = [
            AITeamAgentRun.agent_id == agent_id,
            AITeamAgentRun.organization_id == organization_id,
        ]
        base = select(AITeamAgentRun).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(AITeamAgentRun.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


class AITeamRunRepository(BaseRepository[AITeamRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamRun, session)

    async def get_with_steps(self, run_id: str) -> AITeamRun | None:
        stmt = (
            select(AITeamRun)
            .where(AITeamRun.id == run_id)
            .options(selectinload(AITeamRun.steps))
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_org(self, run_id: str, organization_id: str) -> AITeamRun | None:
        stmt = (
            select(AITeamRun)
            .where(AITeamRun.id == run_id, AITeamRun.organization_id == organization_id)
            .options(selectinload(AITeamRun.steps))
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_team(
        self, team_id: str, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AITeamRun], int]:
        filters = [
            AITeamRun.team_id == team_id,
            AITeamRun.organization_id == organization_id,
        ]
        base = select(AITeamRun).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(AITeamRun.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


class AITeamRunStepRepository(BaseRepository[AITeamRunStep]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamRunStep, session)


class AITeamDocumentRepository(BaseRepository[AITeamDocument]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamDocument, session)

    async def get_for_org(self, document_id: str, organization_id: str) -> AITeamDocument | None:
        stmt = select(AITeamDocument).where(
            AITeamDocument.id == document_id,
            AITeamDocument.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_team(
        self, team_id: str, organization_id: str, *, offset: int = 0, limit: int = 100
    ) -> tuple[list[AITeamDocument], int]:
        filters = [
            AITeamDocument.team_id == team_id,
            AITeamDocument.organization_id == organization_id,
        ]
        base = select(AITeamDocument).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(AITeamDocument.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


class AITeamDocumentChunkRepository(BaseRepository[AITeamDocumentChunk]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamDocumentChunk, session)

    async def list_ready_chunks_for_team(
        self, team_id: str, organization_id: str
    ) -> list[tuple[str, str | None, str]]:
        """Return (content, embedding_json, filename) for READY docs of a team."""
        stmt = (
            select(
                AITeamDocumentChunk.content,
                AITeamDocumentChunk.embedding,
                AITeamDocument.filename,
            )
            .join(AITeamDocument, AITeamDocumentChunk.document_id == AITeamDocument.id)
            .where(
                AITeamDocument.team_id == team_id,
                AITeamDocument.organization_id == organization_id,
                AITeamDocument.status == AITeamDocumentStatus.READY.value,
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return [(r[0], r[1], r[2]) for r in rows]


class AITeamAgentMemoryRepository(BaseRepository[AITeamAgentMemory]):
    """Sprint 39A — persistent per-agent memory store."""

    def __init__(self, session: AsyncSession):
        super().__init__(AITeamAgentMemory, session)

    async def get_for_org(
        self, memory_id: str, organization_id: str
    ) -> AITeamAgentMemory | None:
        stmt = select(AITeamAgentMemory).where(
            AITeamAgentMemory.id == memory_id,
            AITeamAgentMemory.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_agent(
        self,
        agent_id: str,
        organization_id: str,
        *,
        memory_type: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[AITeamAgentMemory], int]:
        filters = [
            AITeamAgentMemory.agent_id == agent_id,
            AITeamAgentMemory.organization_id == organization_id,
        ]
        if memory_type:
            filters.append(AITeamAgentMemory.memory_type == memory_type)
        if search:
            like = f"%{search.strip()}%"
            filters.append(
                or_(
                    AITeamAgentMemory.title.ilike(like),
                    AITeamAgentMemory.content.ilike(like),
                )
            )
        base = select(AITeamAgentMemory).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(
                    AITeamAgentMemory.importance_score.desc(),
                    AITeamAgentMemory.created_at.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def list_all_for_agent(
        self, agent_id: str, organization_id: str
    ) -> list[AITeamAgentMemory]:
        """All of an agent's memories (used for similarity retrieval)."""
        stmt = select(AITeamAgentMemory).where(
            AITeamAgentMemory.agent_id == agent_id,
            AITeamAgentMemory.organization_id == organization_id,
        )
        return list((await self.session.execute(stmt)).scalars().all())


class AITeamToolRepository(BaseRepository[AITeamTool]):
    """Sprint 39B — read-only tool registry."""

    def __init__(self, session: AsyncSession):
        super().__init__(AITeamTool, session)

    async def get_for_org(self, tool_id: str, organization_id: str) -> AITeamTool | None:
        stmt = select(AITeamTool).where(
            AITeamTool.id == tool_id,
            AITeamTool.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        provider: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[AITeamTool], int]:
        filters = [AITeamTool.organization_id == organization_id]
        if provider:
            filters.append(AITeamTool.provider == provider)
        if is_active is not None:
            filters.append(AITeamTool.is_active == is_active)
        return await self.list_all(filters=filters, offset=offset, limit=limit)


class AITeamAgentToolRepository(BaseRepository[AITeamAgentTool]):
    """Sprint 39B — agent↔tool assignments."""

    def __init__(self, session: AsyncSession):
        super().__init__(AITeamAgentTool, session)

    async def get_assignment(
        self, agent_id: str, tool_id: str, organization_id: str
    ) -> AITeamAgentTool | None:
        stmt = select(AITeamAgentTool).where(
            AITeamAgentTool.agent_id == agent_id,
            AITeamAgentTool.tool_id == tool_id,
            AITeamAgentTool.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_tools_for_agent(
        self, agent_id: str, organization_id: str
    ) -> list[AITeamTool]:
        stmt = (
            select(AITeamTool)
            .join(AITeamAgentTool, AITeamAgentTool.tool_id == AITeamTool.id)
            .where(
                AITeamAgentTool.agent_id == agent_id,
                AITeamAgentTool.organization_id == organization_id,
            )
            .order_by(AITeamTool.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class AITeamToolRunRepository(BaseRepository[AITeamToolRun]):
    """Sprint 39B — read-only tool execution history."""

    def __init__(self, session: AsyncSession):
        super().__init__(AITeamToolRun, session)

    async def list_for_tool(
        self, tool_id: str, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AITeamToolRun], int]:
        filters = [
            AITeamToolRun.tool_id == tool_id,
            AITeamToolRun.organization_id == organization_id,
        ]
        base = select(AITeamToolRun).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(AITeamToolRun.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


class AITeamToolCredentialRepository(BaseRepository[AITeamToolCredential]):
    """Sprint 39C — tool↔credential mapping (no secrets stored here)."""

    def __init__(self, session: AsyncSession):
        super().__init__(AITeamToolCredential, session)

    async def get_mapping(
        self, tool_id: str, credential_id: str, organization_id: str
    ) -> AITeamToolCredential | None:
        stmt = select(AITeamToolCredential).where(
            AITeamToolCredential.tool_id == tool_id,
            AITeamToolCredential.credential_id == credential_id,
            AITeamToolCredential.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_tool(
        self, tool_id: str, organization_id: str
    ) -> list[AITeamToolCredential]:
        stmt = (
            select(AITeamToolCredential)
            .where(
                AITeamToolCredential.tool_id == tool_id,
                AITeamToolCredential.organization_id == organization_id,
            )
            .order_by(AITeamToolCredential.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_active_for_tool(
        self, tool_id: str, organization_id: str
    ) -> AITeamToolCredential | None:
        mappings = await self.list_for_tool(tool_id, organization_id)
        return mappings[0] if mappings else None


class AITeamWorkflowRepository(BaseRepository[AITeamWorkflow]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamWorkflow, session)

    async def get_with_steps(self, workflow_id: str) -> AITeamWorkflow | None:
        stmt = (
            select(AITeamWorkflow)
            .where(AITeamWorkflow.id == workflow_id)
            .options(selectinload(AITeamWorkflow.steps))
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_org(self, workflow_id: str, organization_id: str) -> AITeamWorkflow | None:
        stmt = (
            select(AITeamWorkflow)
            .where(
                AITeamWorkflow.id == workflow_id,
                AITeamWorkflow.organization_id == organization_id,
            )
            .options(selectinload(AITeamWorkflow.steps))
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        team_id: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AITeamWorkflow], int]:
        filters = [AITeamWorkflow.organization_id == organization_id]
        if team_id:
            filters.append(AITeamWorkflow.team_id == team_id)
        if is_active is not None:
            filters.append(AITeamWorkflow.is_active == is_active)
        base = select(AITeamWorkflow).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.options(selectinload(AITeamWorkflow.steps))
                .order_by(AITeamWorkflow.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


class AITeamWorkflowStepRepository(BaseRepository[AITeamWorkflowStep]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamWorkflowStep, session)


class AITeamWorkflowScheduleRepository(BaseRepository[AITeamWorkflowSchedule]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamWorkflowSchedule, session)

    async def get_for_org(
        self, schedule_id: str, organization_id: str
    ) -> AITeamWorkflowSchedule | None:
        stmt = select(AITeamWorkflowSchedule).where(
            AITeamWorkflowSchedule.id == schedule_id,
            AITeamWorkflowSchedule.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        workflow_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AITeamWorkflowSchedule], int]:
        filters = [AITeamWorkflowSchedule.organization_id == organization_id]
        if workflow_id:
            filters.append(AITeamWorkflowSchedule.workflow_id == workflow_id)
        base = select(AITeamWorkflowSchedule).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(AITeamWorkflowSchedule.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def list_due(self, now, *, limit: int = 100) -> list[AITeamWorkflowSchedule]:
        """Active schedules whose next_run_at is at or before ``now`` (UTC)."""
        stmt = (
            select(AITeamWorkflowSchedule)
            .where(
                AITeamWorkflowSchedule.is_active.is_(True),
                AITeamWorkflowSchedule.next_run_at.isnot(None),
                AITeamWorkflowSchedule.next_run_at <= now,
            )
            .order_by(AITeamWorkflowSchedule.next_run_at.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def claim_due(
        self, schedule_id: str, expected_next_run_at, new_next_run_at, now
    ) -> bool:
        """Atomically advance a due schedule's next_run_at.

        Conditioned on the currently-stored next_run_at so that only one worker
        process (we run multiple uvicorn workers) can win the claim and execute;
        losers see a 0-row update and skip. Returns True if this caller claimed.
        """
        stmt = (
            update(AITeamWorkflowSchedule)
            .where(
                AITeamWorkflowSchedule.id == schedule_id,
                AITeamWorkflowSchedule.is_active.is_(True),
                AITeamWorkflowSchedule.next_run_at == expected_next_run_at,
            )
            .values(next_run_at=new_next_run_at, last_run_at=now, updated_at=now)
        )
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) == 1


class AITeamWorkflowApprovalRepository(BaseRepository[AITeamWorkflowApproval]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamWorkflowApproval, session)

    async def get_for_org(
        self, approval_id: str, organization_id: str
    ) -> AITeamWorkflowApproval | None:
        stmt = select(AITeamWorkflowApproval).where(
            AITeamWorkflowApproval.id == approval_id,
            AITeamWorkflowApproval.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        workflow_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[AITeamWorkflowApproval], int]:
        filters = [AITeamWorkflowApproval.organization_id == organization_id]
        if workflow_id:
            filters.append(AITeamWorkflowApproval.workflow_id == workflow_id)
        if status:
            filters.append(AITeamWorkflowApproval.status == status)
        base = select(AITeamWorkflowApproval).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(AITeamWorkflowApproval.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def list_for_run(
        self, workflow_run_id: str, organization_id: str
    ) -> list[AITeamWorkflowApproval]:
        stmt = (
            select(AITeamWorkflowApproval)
            .where(
                AITeamWorkflowApproval.workflow_run_id == workflow_run_id,
                AITeamWorkflowApproval.organization_id == organization_id,
            )
            .order_by(AITeamWorkflowApproval.step_order.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class AITeamWorkflowRunRepository(BaseRepository[AITeamWorkflowRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(AITeamWorkflowRun, session)

    async def get_for_org(self, run_id: str, organization_id: str) -> AITeamWorkflowRun | None:
        stmt = select(AITeamWorkflowRun).where(
            AITeamWorkflowRun.id == run_id,
            AITeamWorkflowRun.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_workflow(
        self, workflow_id: str, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AITeamWorkflowRun], int]:
        filters = [
            AITeamWorkflowRun.workflow_id == workflow_id,
            AITeamWorkflowRun.organization_id == organization_id,
        ]
        base = select(AITeamWorkflowRun).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(AITeamWorkflowRun.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)
