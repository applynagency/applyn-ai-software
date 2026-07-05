"""Tool runtime primitives (Sprint 61D)."""

from __future__ import annotations

import asyncio
import enum
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolKind(str, enum.Enum):
    READ = "read"
    WRITE = "write"
    APPROVAL = "approval"  # write that always requires explicit approval


class ToolError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ToolContext:
    session: Any = None
    organization_id: str | None = None
    user_id: str | None = None


@dataclass
class ToolResult:
    name: str
    ok: bool
    output: Any = None
    error: str | None = None
    approval_required: bool = False
    duration_ms: float = 0.0
    attempts: int = 1

    def as_dict(self) -> dict:
        return {
            "tool": self.name, "ok": self.ok, "output": self.output,
            "error": self.error, "approval_required": self.approval_required,
            "duration_ms": round(self.duration_ms, 2), "attempts": self.attempts,
        }


@dataclass
class Tool:
    name: str
    kind: ToolKind
    handler: Callable[[ToolContext, dict], Awaitable[Any]]
    description: str = ""
    parameters: dict = field(default_factory=dict)
    timeout_seconds: float | None = None
    max_retries: int | None = None

    def spec(self) -> dict:
        return {
            "name": self.name, "kind": self.kind.value,
            "description": self.description, "parameters": self.parameters,
            "requires_approval": self.kind == ToolKind.APPROVAL,
        }


_REGISTRY: dict[str, Tool] = {}


def register_tool(tool: Tool) -> None:
    _REGISTRY[tool.name] = tool


def get_tool_registry() -> dict[str, Tool]:
    return dict(_REGISTRY)


class ToolRuntime:
    """Executes registered tools with timeout, retries, sandbox + audit."""

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx

    def list_tools(self) -> list[dict]:
        return [t.spec() for t in _REGISTRY.values()]

    async def execute(
        self, name: str, args: dict | None = None, *, approved: bool = False,
        allow_write: bool = True,
    ) -> ToolResult:
        tool = _REGISTRY.get(name)
        args = args or {}
        if tool is None:
            return ToolResult(name=name, ok=False, error="unknown_tool")

        # Sandbox: a read-only context rejects any mutating tool.
        if not allow_write and tool.kind in (ToolKind.WRITE, ToolKind.APPROVAL):
            return ToolResult(name=name, ok=False, error="sandbox_read_only")

        # Approval gate: approval tools won't run until explicitly approved.
        if tool.kind == ToolKind.APPROVAL and not approved:
            await self._audit(tool, "approval_required", args)
            return ToolResult(name=name, ok=False, approval_required=True,
                              error="approval_required")

        timeout = tool.timeout_seconds or settings.AI_TOOL_DEFAULT_TIMEOUT_SECONDS
        attempts = (tool.max_retries if tool.max_retries is not None
                    else settings.AI_TOOL_MAX_RETRIES) + 1
        start = time.perf_counter()
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            try:
                output = await asyncio.wait_for(
                    tool.handler(self.ctx, args), timeout=timeout)
                duration = (time.perf_counter() - start) * 1000.0
                await self._audit(tool, "executed", args)
                return ToolResult(name=name, ok=True, output=output,
                                  duration_ms=duration, attempts=attempt)
            except TimeoutError:
                last_error = "timeout"
            except ToolError as exc:
                last_error = exc.message
                break  # tool-declared errors are not retried
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            if attempt < attempts:
                await asyncio.sleep(0.1 * attempt)
        duration = (time.perf_counter() - start) * 1000.0
        await self._audit(tool, "failed", args, error=last_error)
        return ToolResult(name=name, ok=False, error=last_error,
                          duration_ms=duration, attempts=attempts)

    async def _audit(self, tool: Tool, action: str, args: dict, error: str | None = None) -> None:
        if self.ctx.session is None:
            return
        try:
            from app.repositories.audit import AuditLogRepository

            await AuditLogRepository(self.ctx.session).log(
                action=f"ai_tool.{action}", resource_type="ai_tool",
                resource_id=tool.name, organization_id=self.ctx.organization_id,
                user_id=self.ctx.user_id,
                details={"kind": tool.kind.value, "args_keys": sorted(args.keys()),
                         "error": error},
                status="success" if action == "executed" else "failure"
                if action == "failed" else "success",
            )
        except Exception:  # pragma: no cover - audit must not break tools
            pass
