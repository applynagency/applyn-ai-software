"""Unified tool runtime (Sprint 61D).

One execution path for every tool an agent or copilot uses: read tools, write
tools, and approval-required tools, with timeout, retries, a read-only sandbox
guard, and audit. Tools are registered in a single registry.
"""

# Register the built-in tool set on import.
from app.ai.tools import builtins as _builtins  # noqa: E402,F401
from app.ai.tools import control_plane as _control_plane  # noqa: E402,F401
from app.ai.tools import delivery as _delivery  # noqa: E402,F401
from app.ai.tools import ops_workspace as _ops_workspace  # noqa: E402,F401
from app.ai.tools import platform_engineering as _platform_engineering  # noqa: E402,F401
from app.ai.tools import ai_operator as _ai_operator  # noqa: E402,F401
from app.ai.tools import k8s_operations as _k8s_operations  # noqa: E402,F401
from app.ai.tools import observability_platform as _observability_platform  # noqa: E402,F401
from app.ai.tools import incident_response as _incident_response  # noqa: E402,F401
from app.ai.tools import security_platform as _security_platform  # noqa: E402,F401
from app.ai.tools.runtime import (
    Tool,
    ToolContext,
    ToolError,
    ToolKind,
    ToolResult,
    ToolRuntime,
    get_tool_registry,
    register_tool,
)

__all__ = [
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolKind",
    "ToolResult",
    "ToolRuntime",
    "register_tool",
    "get_tool_registry",
]
