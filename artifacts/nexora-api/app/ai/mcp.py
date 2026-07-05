"""Model Context Protocol (MCP) support (Sprint 61D).

* :class:`MCPServerService` — CRUD for org-registered remote MCP servers + tool
  discovery (remote tools).
* :class:`MCPClient` — minimal JSON-RPC-over-HTTP client to call remote tools.
* :func:`local_mcp_manifest` — exposes Nexora's local tool registry as an MCP
  server surface (local tools), so Nexora can act as an MCP server too.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools import get_tool_registry
from app.models.ai_platform import MCPServer
from app.repositories.audit import AuditLogRepository


def _now() -> datetime:
    return datetime.now(UTC)


class MCPError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def local_mcp_manifest() -> dict:
    """Nexora-as-MCP-server: expose local tools in MCP tool-manifest shape."""
    tools = []
    for tool in get_tool_registry().values():
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.parameters or {"type": "object", "properties": {}},
            "annotations": {"kind": tool.kind.value,
                            "requiresApproval": tool.kind.value == "approval"},
        })
    return {"protocol": "mcp", "version": "2024-11-05", "tools": tools}


class MCPClient:
    """Talks to a remote MCP server (HTTP transport, JSON-RPC 2.0)."""

    def __init__(self, server: MCPServer) -> None:
        self.server = server

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.server.auth_token:
            headers["Authorization"] = f"Bearer {self.server.auth_token}"
        return headers

    async def _rpc(self, method: str, params: dict | None = None) -> dict:  # pragma: no cover - network
        import httpx

        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(self.server.url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            raise MCPError(str(data["error"]))
        return data.get("result", {})

    async def list_tools(self) -> list[dict]:  # pragma: no cover - network
        result = await self._rpc("tools/list")
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:  # pragma: no cover - network
        return await self._rpc("tools/call", {"name": name, "arguments": arguments})


class MCPServerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def register(
        self, *, organization_id: str, name: str, url: str,
        transport: str = "http", auth_token: str | None = None,
        actor_user_id: str | None = None,
    ) -> MCPServer:
        existing = await self.session.scalar(
            select(MCPServer).where(
                MCPServer.organization_id == organization_id, MCPServer.name == name)
        )
        if existing is not None:
            raise MCPError(f"MCP server '{name}' already registered", status_code=409)
        server = MCPServer(
            organization_id=organization_id, name=name, url=url,
            transport=transport, auth_token=auth_token, is_active=True,
        )
        self.session.add(server)
        await self.session.flush()
        await self.audit.log(
            action="mcp.server_registered", resource_type="mcp_server",
            resource_id=server.id, organization_id=organization_id, user_id=actor_user_id,
            details={"name": name, "url": url, "transport": transport},
        )
        return server

    async def list_servers(self, organization_id: str) -> list[MCPServer]:
        return list((await self.session.execute(
            select(MCPServer).where(MCPServer.organization_id == organization_id)
        )).scalars().all())

    async def get(self, organization_id: str, server_id: str) -> MCPServer | None:
        server = await self.session.get(MCPServer, server_id)
        if server is None or server.organization_id != organization_id:
            return None
        return server

    async def deregister(self, organization_id: str, server_id: str, *, actor_user_id: str | None = None) -> bool:
        server = await self.get(organization_id, server_id)
        if server is None:
            return False
        await self.session.delete(server)
        await self.session.flush()
        await self.audit.log(
            action="mcp.server_deregistered", resource_type="mcp_server",
            resource_id=server_id, organization_id=organization_id, user_id=actor_user_id,
            details={"name": server.name},
        )
        return True

    async def sync_tools(self, organization_id: str, server_id: str) -> list[dict]:
        """Discover remote tools. Falls back to cached/empty when unreachable."""
        server = await self.get(organization_id, server_id)
        if server is None:
            raise MCPError("MCP server not found", status_code=404)
        try:
            tools = await MCPClient(server).list_tools()
        except Exception:  # noqa: BLE001 - offline/dev: keep cached
            tools = server.discovered_tools or []
        server.discovered_tools = tools
        server.last_synced_at = _now()
        self.session.add(server)
        await self.session.flush()
        return tools
