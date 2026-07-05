"""Built-in tools registered with the unified runtime (Sprint 61D).

These are intentionally lightweight/safe defaults that demonstrate each tool
kind (read / write / approval). Domain tools (discovery, graph, incidents) can
register additional tools via ``register_tool``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.tools.runtime import Tool, ToolContext, ToolKind, register_tool


async def _echo(ctx: ToolContext, args: dict):
    return {"echo": args.get("text", "")}


async def _current_time(ctx: ToolContext, args: dict):
    return {"now": datetime.now(UTC).isoformat()}


async def _record_note(ctx: ToolContext, args: dict):
    # A trivial "write" tool — persists nothing externally but represents a
    # mutating action subject to the sandbox guard.
    return {"recorded": True, "note": args.get("note", "")}


async def _apply_change(ctx: ToolContext, args: dict):
    # An approval-required action.
    return {"applied": True, "change": args.get("change", "")}


def register_builtin_tools() -> None:
    register_tool(Tool(
        name="echo", kind=ToolKind.READ, handler=_echo,
        description="Echo back input text.",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
    ))
    register_tool(Tool(
        name="current_time", kind=ToolKind.READ, handler=_current_time,
        description="Return the current UTC time.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="record_note", kind=ToolKind.WRITE, handler=_record_note,
        description="Record a note (mutating).",
        parameters={"type": "object", "properties": {"note": {"type": "string"}}},
    ))
    register_tool(Tool(
        name="apply_change", kind=ToolKind.APPROVAL, handler=_apply_change,
        description="Apply a change (requires approval).",
        parameters={"type": "object", "properties": {"change": {"type": "string"}}},
    ))


register_builtin_tools()
