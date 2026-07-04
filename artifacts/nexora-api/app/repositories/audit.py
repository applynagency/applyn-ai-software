import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import utcnow
from app.models.audit import AuditLog
from app.repositories.base import BaseRepository
from app.services.audit.hashing import row_hash


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        organization_id: str | None = None,
    ) -> AuditLog:
        """Append a tamper-evident audit entry to the organization's hash chain.

        ``organization_id`` falls back to ``details['organization_id']`` so the
        many existing callers that already carry the org in ``details`` are
        chained correctly without code changes.
        """
        org_id = organization_id or (details or {}).get("organization_id")

        last = await self._last_in_chain(org_id)
        sequence = (last.sequence + 1) if last and last.sequence is not None else 0
        prev_hash = last.entry_hash if last else None

        entry = AuditLog(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            sequence=sequence,
            prev_hash=prev_hash,
            created_at=utcnow(),
        )
        entry.entry_hash = row_hash(entry)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def _last_in_chain(self, organization_id: str | None) -> AuditLog | None:
        stmt = select(AuditLog)
        if organization_id is None:
            stmt = stmt.where(AuditLog.organization_id.is_(None))
        else:
            stmt = stmt.where(AuditLog.organization_id == organization_id)
        stmt = stmt.order_by(
            AuditLog.sequence.desc(), AuditLog.created_at.desc(), AuditLog.id.desc()
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _scope_filters(
        self,
        organization_id: str | None,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list:
        filters: list = []
        if organization_id is None:
            filters.append(AuditLog.organization_id.is_(None))
        else:
            filters.append(AuditLog.organization_id == organization_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if resource_id:
            filters.append(AuditLog.resource_id == resource_id)
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if status:
            filters.append(AuditLog.status == status)
        if start:
            filters.append(AuditLog.created_at >= start)
        if end:
            filters.append(AuditLog.created_at <= end)
        return filters

    async def list_filtered(
        self,
        organization_id: str | None,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
        ascending: bool = False,
    ) -> tuple[list[AuditLog], int]:
        filters = self._scope_filters(
            organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            status=status,
            start=start,
            end=end,
        )
        order = AuditLog.sequence.asc() if ascending else AuditLog.sequence.desc()
        return await self._paginate(filters, order, offset, limit)

    async def _paginate(self, filters, order, offset, limit):
        from sqlalchemy import and_, func

        where = and_(*filters)
        total_result = await self.session.execute(
            select(func.count()).select_from(AuditLog).where(where)
        )
        total = int(total_result.scalar_one())
        data_result = await self.session.execute(
            select(AuditLog)
            .where(where)
            .order_by(order, AuditLog.created_at.asc(), AuditLog.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(data_result.scalars().all()), total

    async def list_chain(self, organization_id: str | None) -> list[AuditLog]:
        """All entries in a chain, in chain order (for integrity verification)."""
        stmt = select(AuditLog)
        if organization_id is None:
            stmt = stmt.where(AuditLog.organization_id.is_(None))
        else:
            stmt = stmt.where(AuditLog.organization_id == organization_id)
        stmt = stmt.order_by(
            AuditLog.sequence.asc(), AuditLog.created_at.asc(), AuditLog.id.asc()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_team(
        self, team_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AuditLog], int]:
        team_actions = {
            "team_created",
            "team_updated",
            "team_deleted",
            "team_archived",
            "team_duplicated",
            "responsibility_created",
            "responsibility_updated",
            "responsibility_deleted",
            "template_applied",
        }
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type.in_(["team", "team_responsibility", "team_template"]),
            )
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = [
            log
            for log in result.scalars().all()
            if log.action in team_actions
            and (
                log.resource_id == team_id
                or (log.details or {}).get("team_id") == team_id
                or (log.details or {}).get("source_team_id") == team_id
            )
        ]
        return items, len(items)

    async def list_for_workflow(
        self, workflow_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AuditLog], int]:
        workflow_actions = {
            "workflow_created",
            "workflow_updated",
            "workflow_deleted",
            "workflow_archived",
            "workflow_duplicated",
            "workflow_template_applied",
            "stage_created",
            "stage_updated",
            "stage_deleted",
            "team_assigned",
            "rule_created",
        }
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type.in_(
                    [
                        "workflow",
                        "workflow_stage",
                        "workflow_stage_team",
                        "workflow_rule",
                        "workflow_template",
                    ]
                ),
            )
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = [
            log
            for log in result.scalars().all()
            if log.action in workflow_actions
            and (
                log.resource_id == workflow_id
                or (log.details or {}).get("workflow_id") == workflow_id
            )
        ]
        return items, len(items)

    async def list_for_workflow_execution(
        self, execution_id: str, *, offset: int = 0, limit: int = 100
    ) -> tuple[list[AuditLog], int]:
        execution_actions = {
            "workflow_execution_started",
            "workflow_execution_completed",
            "workflow_execution_failed",
            "workflow_execution_waiting_for_approval",
            "workflow_execution_resumed",
            "stage_started",
            "stage_completed",
            "agent_started",
            "agent_completed",
        }
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type.in_(
                    [
                        "workflow_execution",
                        "workflow_execution_stage",
                        "workflow_execution_agent",
                    ]
                ),
            )
            .order_by(AuditLog.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = [
            log
            for log in result.scalars().all()
            if log.action in execution_actions
            and (
                log.resource_id == execution_id
                or (log.details or {}).get("execution_id") == execution_id
            )
        ]
        return items, len(items)

    async def list_for_ai_team(
        self, team_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AuditLog], int]:
        team_actions = {
            "ai_team_created",
            "ai_team_updated",
            "ai_team_deleted",
            "ai_agent_created",
            "ai_agent_updated",
            "ai_agent_deleted",
            "ai_agent_executed",
            "ai_agent_execution_failed",
            "ai_team_execution_started",
            "ai_team_execution_completed",
            "ai_team_execution_failed",
            "ai_document_uploaded",
            "ai_document_processed",
            "ai_document_deleted",
        }
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type.in_(
                    ["ai_team", "ai_team_agent", "ai_team_document"]
                ),
            )
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = [
            log
            for log in result.scalars().all()
            if log.action in team_actions
            and (
                log.resource_id == team_id
                or (log.details or {}).get("team_id") == team_id
            )
        ]
        return items, len(items)

    async def list_for_ai_agent(
        self, agent_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[AuditLog], int]:
        agent_actions = {
            "agent_created",
            "agent_updated",
            "agent_deleted",
            "agent_archived",
            "agent_duplicated",
            "agent_template_applied",
            "agent_assigned",
            "input_created",
            "output_created",
            "responsibility_created",
        }
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type.in_(
                    [
                        "ai_agent",
                        "ai_agent_input",
                        "ai_agent_output",
                        "ai_agent_responsibility",
                        "ai_agent_workflow_assignment",
                        "ai_agent_template",
                    ]
                ),
            )
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = [
            log
            for log in result.scalars().all()
            if log.action in agent_actions
            and (
                log.resource_id == agent_id
                or (log.details or {}).get("agent_id") == agent_id
            )
        ]
        return items, len(items)
