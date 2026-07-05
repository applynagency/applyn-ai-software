"""Unified agent runtime (Sprint 61D).

A single planning/execution loop every AI Team can use:

* memory       — episodic memory of each run (via MemoryService)
* planning     — decompose a goal into ordered steps
* execution    — run steps through the AI gateway + tool runtime
* retries      — gateway-level retries + fallback are inherited
* checkpoints  — persisted after each step for resume
* approvals    — approval steps pause the run until approved
* cancellation — cooperative cancel between steps
* resume       — continue from the last checkpoint
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.memory import MemoryService
from app.ai.types import LLMMessage, LLMRequest
from app.core.config import settings
from app.models.ai_platform import AIAgentRun, AIAgentRunStatus, MemoryScope
from app.repositories.audit import AuditLogRepository


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AgentRuntimeError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _plan_for_goal(goal: str, steps: list[dict] | None) -> list[dict]:
    if steps:
        return [
            {"id": i, "description": s.get("description", ""),
             "kind": s.get("kind", "respond"), "tool": s.get("tool"),
             "args": s.get("args", {})}
            for i, s in enumerate(steps)
        ]
    # Deterministic decomposition: split on sentence/line boundaries.
    parts = [p.strip() for p in goal.replace(";", "\n").split("\n") if p.strip()]
    if len(parts) <= 1:
        return [{"id": 0, "description": goal, "kind": "respond", "tool": None, "args": {}}]
    return [
        {"id": i, "description": p, "kind": "respond", "tool": None, "args": {}}
        for i, p in enumerate(parts)
    ]


class AgentRuntime:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = AIGateway(session)
        self.memory = MemoryService(session)
        self.audit = AuditLogRepository(session)

    async def start(
        self, *, organization_id: str, agent_key: str, goal: str,
        user_id: str | None = None, steps: list[dict] | None = None,
    ) -> AIAgentRun:
        plan = _plan_for_goal(goal, steps)
        run = AIAgentRun(
            organization_id=organization_id, user_id=user_id, agent_key=agent_key,
            goal=goal, status=AIAgentRunStatus.PLANNING.value, plan=plan,
            current_step=0, checkpoints=[],
        )
        self.session.add(run)
        await self.session.flush()
        await self.audit.log(
            action="ai_agent.started", resource_type="ai_agent_run", resource_id=run.id,
            organization_id=organization_id, user_id=user_id,
            details={"agent_key": agent_key, "steps": len(plan)},
        )
        return run

    async def get(self, organization_id: str, run_id: str) -> AIAgentRun | None:
        run = await self.session.get(AIAgentRun, run_id)
        if run is None or run.organization_id != organization_id:
            return None
        return run

    async def run_to_completion(self, organization_id: str, run_id: str) -> AIAgentRun:
        run = await self.get(organization_id, run_id)
        if run is None:
            raise AgentRuntimeError("Agent run not found", status_code=404)
        if run.status in (AIAgentRunStatus.COMPLETED.value, AIAgentRunStatus.CANCELLED.value,
                          AIAgentRunStatus.FAILED.value):
            return run

        run.status = AIAgentRunStatus.RUNNING.value
        plan = run.plan or []
        checkpoints = list(run.checkpoints or [])
        max_steps = settings.AI_AGENT_MAX_STEPS

        while run.current_step < len(plan) and run.current_step < max_steps:
            # Cooperative cancellation between steps (re-read from the DB so a
            # cancel issued by another process/request is observed).
            await self.session.flush()
            try:
                await self.session.refresh(run, ["cancel_requested"])
            except Exception:  # noqa: BLE001 - refresh is best-effort
                pass
            if run.cancel_requested:
                run.status = AIAgentRunStatus.CANCELLED.value
                await self._finish(run, checkpoints, error="cancelled")
                return run

            step = plan[run.current_step]
            if step.get("kind") == "approval":
                run.status = AIAgentRunStatus.WAITING_APPROVAL.value
                run.pending_approval = {"step": run.current_step,
                                        "description": step.get("description")}
                run.checkpoints = checkpoints
                self.session.add(run)
                await self.session.flush()
                return run

            output = await self._execute_step(run, step)
            checkpoints.append({
                "step": run.current_step, "description": step.get("description"),
                "output": output, "ts": _now_iso(),
            })
            run.current_step += 1
            run.checkpoints = checkpoints
            self.session.add(run)
            await self.session.flush()

        run.status = AIAgentRunStatus.COMPLETED.value
        await self._finish(run, checkpoints)
        # Episodic memory of the run.
        await self.memory.remember(
            organization_id=organization_id, scope=MemoryScope.EPISODIC,
            namespace=f"agent:{run.agent_key}", user_id=run.user_id,
            content=f"Goal: {run.goal}\nResult: {run.result}", importance=0.6,
        )
        return run

    async def _execute_step(self, run: AIAgentRun, step: dict) -> dict:
        # Tool step.
        if step.get("tool"):
            from app.ai.tools import ToolContext, ToolRuntime

            ctx = ToolContext(session=self.session, organization_id=run.organization_id,
                              user_id=run.user_id)
            result = await ToolRuntime(ctx).execute(step["tool"], step.get("args", {}))
            return result.as_dict()

        # Generation step via the gateway.
        req = LLMRequest(
            messages=[LLMMessage(role="user", content=step.get("description", run.goal))],
            system=f"You are agent '{run.agent_key}'. Work towards: {run.goal}",
            feature=f"agent:{run.agent_key}", organization_id=run.organization_id,
            user_id=run.user_id, temperature=0.2,
        )
        resp = await self.gateway.complete(req)
        run.tokens_used += resp.usage.total_tokens
        run.cost_usd += resp.cost_usd
        return {"text": resp.text, "provider": resp.provider, "model": resp.model,
                "tokens": resp.usage.total_tokens}

    async def approve(self, organization_id: str, run_id: str, *, actor_user_id: str | None = None) -> AIAgentRun:
        run = await self.get(organization_id, run_id)
        if run is None:
            raise AgentRuntimeError("Agent run not found", status_code=404)
        if run.status != AIAgentRunStatus.WAITING_APPROVAL.value:
            raise AgentRuntimeError("Run is not awaiting approval")
        # Execute the approval step, then continue.
        plan = run.plan or []
        step = plan[run.current_step] if run.current_step < len(plan) else None
        checkpoints = list(run.checkpoints or [])
        if step is not None:
            from app.ai.tools import ToolContext, ToolRuntime

            ctx = ToolContext(session=self.session, organization_id=organization_id,
                              user_id=run.user_id)
            output = {"approved": True}
            if step.get("tool"):
                output = (await ToolRuntime(ctx).execute(
                    step["tool"], step.get("args", {}), approved=True)).as_dict()
            checkpoints.append({"step": run.current_step, "approved": True,
                                "output": output, "ts": _now_iso()})
            run.current_step += 1
        run.pending_approval = None
        run.checkpoints = checkpoints
        run.status = AIAgentRunStatus.RUNNING.value
        self.session.add(run)
        await self.session.flush()
        await self.audit.log(
            action="ai_agent.approved", resource_type="ai_agent_run", resource_id=run.id,
            organization_id=organization_id, user_id=actor_user_id,
            details={"step": run.current_step - 1},
        )
        return await self.run_to_completion(organization_id, run_id)

    async def cancel(self, organization_id: str, run_id: str, *, actor_user_id: str | None = None) -> AIAgentRun:
        run = await self.get(organization_id, run_id)
        if run is None:
            raise AgentRuntimeError("Agent run not found", status_code=404)
        run.cancel_requested = True
        if run.status in (AIAgentRunStatus.WAITING_APPROVAL.value, AIAgentRunStatus.PAUSED.value,
                          AIAgentRunStatus.PENDING.value, AIAgentRunStatus.PLANNING.value):
            run.status = AIAgentRunStatus.CANCELLED.value
        self.session.add(run)
        await self.session.flush()
        await self.audit.log(
            action="ai_agent.cancelled", resource_type="ai_agent_run", resource_id=run.id,
            organization_id=organization_id, user_id=actor_user_id, details={},
        )
        return run

    async def resume(self, organization_id: str, run_id: str) -> AIAgentRun:
        run = await self.get(organization_id, run_id)
        if run is None:
            raise AgentRuntimeError("Agent run not found", status_code=404)
        if run.status == AIAgentRunStatus.WAITING_APPROVAL.value:
            raise AgentRuntimeError("Run awaits approval; call approve")
        if run.status in (AIAgentRunStatus.COMPLETED.value, AIAgentRunStatus.CANCELLED.value):
            return run
        return await self.run_to_completion(organization_id, run_id)

    async def _finish(self, run: AIAgentRun, checkpoints: list, error: str | None = None) -> None:
        run.checkpoints = checkpoints
        if error:
            run.error = error
        else:
            run.result = {
                "steps": len(checkpoints),
                "summary": checkpoints[-1]["output"] if checkpoints else None,
                "tokens_used": run.tokens_used, "cost_usd": round(run.cost_usd, 6),
            }
        self.session.add(run)
        await self.session.flush()
        await self.audit.log(
            action=f"ai_agent.{run.status}", resource_type="ai_agent_run",
            resource_id=run.id, organization_id=run.organization_id,
            user_id=run.user_id, details={"steps": len(checkpoints)},
        )
