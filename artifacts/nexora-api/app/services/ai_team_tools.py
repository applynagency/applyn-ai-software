"""Sprint 39B — Agent Tool Integrations (read-only foundation).

Lets customer AI Team Agents securely *investigate* real engineering/infra
systems through a fixed allow-list of read-only operations. There are no
mutating actions: every execution is validated against the registry, denied if
it looks like a write/destroy/deploy/shell, audited, and recorded with a
sanitized (secret-free) payload + customer-safe summary.

Strictly additive: this service does not touch AI Team CRUD, agent execution,
collaboration, knowledge base, memory, workflows, schedules, or approvals.
"""

import json
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.core.logging import get_logger
from app.models.ai_team import AITeamToolRun, AITeamToolRunStatus
from app.models.user import User
from app.repositories.ai_team import (
    AITeamAgentToolRepository,
    AITeamToolCredentialRepository,
    AITeamToolRepository,
    AITeamToolRunRepository,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.credential import DeploymentCredentialRepository
from app.schemas.ai_team import (
    AITeamToolAssignRequest,
    AITeamToolConnectionStatusResponse,
    AITeamToolCreate,
    AITeamToolCredentialAttachRequest,
    AITeamToolCredentialResponse,
    AITeamToolExecuteRequest,
    AITeamToolExecuteResponse,
    AITeamToolListResponse,
    AITeamToolResponse,
    AITeamToolRunListResponse,
    AITeamToolRunResponse,
    AITeamToolUpdate,
    AITeamToolVerifyResponse,
)
from app.services import tool_connectors
from app.services.tool_connectors import ConnectorError, provider_has_real_connector
from app.services.tool_registry import (
    PROVIDER_ACTIONS,
    execute_readonly,
    sanitize_payload,
    validate_action,
)
from app.tenancy.guards import get_ai_team_agent_for_org
from app.tenancy.permissions import (
    can_manage_ai_teams,
    can_read_ai_teams,
    can_write_ai_teams,
)

logger = get_logger(__name__)


class AITeamToolService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tool_repo = AITeamToolRepository(session)
        self.assign_repo = AITeamAgentToolRepository(session)
        self.run_repo = AITeamToolRunRepository(session)
        self.cred_repo = AITeamToolCredentialRepository(session)
        self.deployment_cred_repo = DeploymentCredentialRepository(session)
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
    def _tool_to_response(self, tool) -> AITeamToolResponse:
        resp = AITeamToolResponse.model_validate(tool)
        resp.allowed_actions = sorted(PROVIDER_ACTIONS.get(tool.provider, {}).keys())
        return resp

    # ------------------------------------------------------------- tool CRUD
    async def list_tools(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        provider: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> AITeamToolListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.tool_repo.list_by_organization(
            organization_id,
            provider=provider.upper() if provider else None,
            is_active=is_active,
            offset=offset,
            limit=limit,
        )
        return AITeamToolListResponse(
            items=[self._tool_to_response(t) for t in items], total=total
        )

    async def create_tool(
        self, data: AITeamToolCreate, current_user: User, org_context: OrgContext
    ) -> AITeamToolResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        tool = await self.tool_repo.create(
            organization_id=organization_id,
            provider=data.provider,
            name=data.name.strip(),
            description=(data.description or None),
            is_active=data.is_active,
        )
        await self.audit_repo.log(
            action="tool_created",
            resource_type="ai_team_tool",
            resource_id=tool.id,
            user_id=current_user.id,
            details={"tool_id": tool.id, "provider": tool.provider},
        )
        logger.info("ai_tool_created", tool_id=tool.id, provider=tool.provider)
        return self._tool_to_response(tool)

    async def get_tool(
        self, tool_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamToolResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        tool = await self.tool_repo.get_for_org(tool_id, organization_id)
        if tool is None:
            raise NexoraException("Tool not found.", status_code=404)
        return self._tool_to_response(tool)

    async def update_tool(
        self,
        tool_id: str,
        data: AITeamToolUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamToolResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        tool = await self.tool_repo.get_for_org(tool_id, organization_id)
        if tool is None:
            raise NexoraException("Tool not found.", status_code=404)
        fields: dict = {}
        if data.name is not None:
            fields["name"] = data.name.strip()
        if data.description is not None:
            fields["description"] = data.description or None
        if data.is_active is not None:
            fields["is_active"] = data.is_active
        if fields:
            tool = await self.tool_repo.update(tool, **fields)
        await self.audit_repo.log(
            action="tool_updated",
            resource_type="ai_team_tool",
            resource_id=tool.id,
            user_id=current_user.id,
            details={"tool_id": tool.id},
        )
        return self._tool_to_response(tool)

    async def delete_tool(
        self, tool_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        organization_id = org_context.requires_organization
        self._ensure_manage(current_user, org_context)
        tool = await self.tool_repo.get_for_org(tool_id, organization_id)
        if tool is None:
            raise NexoraException("Tool not found.", status_code=404)
        await self.tool_repo.hard_delete(tool)
        await self.audit_repo.log(
            action="tool_deleted",
            resource_type="ai_team_tool",
            resource_id=tool_id,
            user_id=current_user.id,
            details={"tool_id": tool_id},
        )

    # --------------------------------------------------------- assignments
    async def assign_tool(
        self,
        agent_id: str,
        data: AITeamToolAssignRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamToolListResponse:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        tool = await self.tool_repo.get_for_org(data.tool_id, agent.organization_id)
        if tool is None:
            raise NexoraException("Tool not found.", status_code=404)
        existing = await self.assign_repo.get_assignment(
            agent.id, tool.id, agent.organization_id
        )
        if existing is None:
            await self.assign_repo.create(
                organization_id=agent.organization_id,
                agent_id=agent.id,
                tool_id=tool.id,
            )
            await self.audit_repo.log(
                action="tool_assigned",
                resource_type="ai_team_tool",
                resource_id=tool.id,
                user_id=current_user.id,
                details={"tool_id": tool.id, "agent_id": agent.id},
            )
        return await self.list_agent_tools(agent_id, current_user, org_context)

    async def unassign_tool(
        self,
        agent_id: str,
        tool_id: str,
        current_user: User,
        org_context: OrgContext,
    ) -> None:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_write(current_user, org_context)
        assignment = await self.assign_repo.get_assignment(
            agent.id, tool_id, agent.organization_id
        )
        if assignment is None:
            raise NexoraException("Tool assignment not found.", status_code=404)
        await self.assign_repo.hard_delete(assignment)
        await self.audit_repo.log(
            action="tool_unassigned",
            resource_type="ai_team_tool",
            resource_id=tool_id,
            user_id=current_user.id,
            details={"tool_id": tool_id, "agent_id": agent.id},
        )

    async def list_agent_tools(
        self, agent_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamToolListResponse:
        agent = await get_ai_team_agent_for_org(self.session, agent_id, org_context)
        self._ensure_read(current_user, org_context)
        tools = await self.assign_repo.list_tools_for_agent(
            agent.id, agent.organization_id
        )
        return AITeamToolListResponse(
            items=[self._tool_to_response(t) for t in tools], total=len(tools)
        )

    # ---------------------------------------------------------- execution
    async def execute_tool(
        self,
        tool_id: str,
        data: AITeamToolExecuteRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamToolExecuteResponse:
        organization_id = org_context.requires_organization
        tool = await self.tool_repo.get_for_org(tool_id, organization_id)
        if tool is None:
            # Tenant isolation: cross-org or unknown tool is indistinguishable.
            raise NexoraException("Tool not found.", status_code=404)
        self._ensure_write(current_user, org_context)
        # Resolve + authorize the agent (404 on cross-org).
        agent = await get_ai_team_agent_for_org(self.session, data.agent_id, org_context)

        # The tool must be explicitly assigned to this agent.
        assignment = await self.assign_repo.get_assignment(
            agent.id, tool.id, organization_id
        )
        if assignment is None:
            raise NexoraException(
                "This tool is not assigned to the agent.", status_code=403
            )
        if not tool.is_active:
            raise NexoraException("This tool is currently disabled.", status_code=400)

        sanitized = sanitize_payload(data.payload)
        payload_json = json.dumps(sanitized) if sanitized else None

        # Read-only enforcement. A denial is itself persisted + audited.
        try:
            normalized = validate_action(tool.provider, data.action, data.payload)
        except NexoraException as exc:
            run = await self.run_repo.create(
                organization_id=organization_id,
                agent_id=agent.id,
                tool_id=tool.id,
                action=(data.action or "")[:120],
                status=AITeamToolRunStatus.DENIED.value,
                request_payload=payload_json,
                response_summary=None,
                error_message=getattr(exc, "message", str(exc)),
                execution_time_ms=0,
            )
            await self.audit_repo.log(
                action="tool_execution_denied",
                resource_type="ai_team_tool",
                resource_id=tool.id,
                user_id=current_user.id,
                details={
                    "tool_id": tool.id,
                    "agent_id": agent.id,
                    "run_id": run.id,
                    "action": (data.action or "")[:120],
                },
                status="failure",
            )
            # Persist the DENIED run + audit before re-raising; the request
            # session would otherwise roll them back on the exception.
            await self.session.commit()
            logger.info("ai_tool_denied", tool_id=tool.id, run_id=run.id)
            raise

        # Sprint 39C — if a real credential is attached and the provider has a
        # real connector, investigate live infrastructure with the customer's
        # decrypted credential. Otherwise fall back to the 39B simulated read
        # (unchanged behavior for unconfigured/SLACK/JIRA tools).
        mapping = await self.cred_repo.get_active_for_tool(tool.id, organization_id)
        use_real = mapping is not None and provider_has_real_connector(tool.provider)

        credential = None
        secret = None
        secret_service = None
        if use_real:
            from app.security.secrets import SecretManagerService

            secret_service = SecretManagerService(self.session)
            try:
                # Decrypt transiently; defer SECRET_USED audit until we have a run id.
                credential, secret = await secret_service.resolve_secret(
                    mapping.credential_id,
                    user=current_user,
                    org_context=org_context,
                    reason="ai team tool execution",
                    audit=False,
                )
            except NexoraException:
                run = await self.run_repo.create(
                    organization_id=organization_id,
                    agent_id=agent.id,
                    tool_id=tool.id,
                    action=normalized,
                    status=AITeamToolRunStatus.FAILED.value,
                    request_payload=payload_json,
                    response_summary=None,
                    error_message="The attached credential is unavailable or revoked.",
                    execution_time_ms=0,
                )
                await self.audit_repo.log(
                    action="tool_execution_failed",
                    resource_type="ai_team_tool",
                    resource_id=tool.id,
                    user_id=current_user.id,
                    details={"tool_id": tool.id, "agent_id": agent.id, "run_id": run.id},
                    status="failure",
                )
                await self.session.commit()
                raise NexoraException(
                    "The attached credential is unavailable or revoked.",
                    status_code=400,
                )

        mode = "REAL" if use_real else "SIMULATED"
        start = time.monotonic()
        try:
            if use_real:
                summary = await tool_connectors.execute_real(
                    tool.provider, normalized, secret, data.payload
                )
            else:
                summary = execute_readonly(tool.provider, normalized, data.payload)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            run = await self.run_repo.create(
                organization_id=organization_id,
                agent_id=agent.id,
                tool_id=tool.id,
                action=normalized,
                status=AITeamToolRunStatus.COMPLETED.value,
                request_payload=payload_json,
                response_summary=summary,
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001 - normalize to customer-safe error
            elapsed_ms = int((time.monotonic() - start) * 1000)
            # ConnectorError messages are already customer-safe; anything else
            # collapses to a generic message so no driver/secret text leaks.
            safe_msg = (
                str(exc)
                if isinstance(exc, ConnectorError)
                else "The tool could not complete the request."
            )
            run = await self.run_repo.create(
                organization_id=organization_id,
                agent_id=agent.id,
                tool_id=tool.id,
                action=normalized,
                status=AITeamToolRunStatus.FAILED.value,
                request_payload=payload_json,
                response_summary=None,
                error_message=safe_msg,
                execution_time_ms=elapsed_ms,
            )
            await self.audit_repo.log(
                action="tool_execution_failed",
                resource_type="ai_team_tool",
                resource_id=tool.id,
                user_id=current_user.id,
                details={
                    "tool_id": tool.id,
                    "agent_id": agent.id,
                    "run_id": run.id,
                    "mode": mode,
                },
                status="failure",
            )
            if use_real and credential is not None and secret_service is not None:
                # The credential was used (attempted), so audit SECRET_USED.
                await secret_service.record_usage(
                    credential,
                    user=current_user,
                    org_context=org_context,
                    deployment_id=run.id,
                    reason="ai team tool execution",
                )
            await self.session.commit()
            logger.error("ai_tool_failed", tool_id=tool.id, mode=mode, error=type(exc).__name__)
            raise NexoraException(safe_msg, status_code=502) from exc

        if use_real and credential is not None and secret_service is not None:
            await secret_service.record_usage(
                credential,
                user=current_user,
                org_context=org_context,
                deployment_id=run.id,
                reason="ai team tool execution",
            )

        await self.audit_repo.log(
            action="tool_executed",
            resource_type="ai_team_tool",
            resource_id=tool.id,
            user_id=current_user.id,
            details={
                "tool_id": tool.id,
                "agent_id": agent.id,
                "run_id": run.id,
                "provider": tool.provider,
                "action": normalized,
                "mode": mode,
            },
        )
        logger.info(
            "ai_tool_executed", tool_id=tool.id, run_id=run.id, action=normalized, mode=mode
        )
        return AITeamToolExecuteResponse(
            run_id=run.id,
            tool_id=tool.id,
            agent_id=agent.id,
            provider=tool.provider,
            action=normalized,
            status=AITeamToolRunStatus.COMPLETED.value,
            response_summary=summary,
            error_message=None,
            execution_time_ms=elapsed_ms,
        )

    async def run_readonly_action(
        self,
        *,
        tool,
        agent,
        action: str,
        payload: dict | None,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamToolRun:
        """Execute one read-only tool action and record an audited run.

        Sprint 40A reuse hook: assumes the caller has already authorized the
        tool/agent and confirmed assignment (e.g. the incident engine). Unlike
        ``execute_tool`` this never raises on a tool/connector failure — it
        records and returns a FAILED ``AITeamToolRun`` so a multi-tool
        investigation can continue. Read-only enforcement, credential resolution,
        secret-usage auditing, and payload sanitization are identical.
        """

        organization_id = org_context.requires_organization
        sanitized = sanitize_payload(payload)
        payload_json = json.dumps(sanitized) if sanitized else None

        # Read-only enforcement (defense in depth even though callers pre-pick).
        try:
            normalized = validate_action(tool.provider, action, payload)
        except NexoraException as exc:
            run = await self.run_repo.create(
                organization_id=organization_id,
                agent_id=agent.id,
                tool_id=tool.id,
                action=(action or "")[:120],
                status=AITeamToolRunStatus.DENIED.value,
                request_payload=payload_json,
                response_summary=None,
                error_message=getattr(exc, "message", str(exc)),
                execution_time_ms=0,
            )
            return run

        mapping = await self.cred_repo.get_active_for_tool(tool.id, organization_id)
        use_real = mapping is not None and provider_has_real_connector(tool.provider)
        credential = None
        secret = None
        secret_service = None
        if use_real:
            from app.security.secrets import SecretManagerService

            secret_service = SecretManagerService(self.session)
            try:
                credential, secret = await secret_service.resolve_secret(
                    mapping.credential_id,
                    user=current_user,
                    org_context=org_context,
                    reason="incident investigation",
                    audit=False,
                )
            except NexoraException:
                return await self.run_repo.create(
                    organization_id=organization_id,
                    agent_id=agent.id,
                    tool_id=tool.id,
                    action=normalized,
                    status=AITeamToolRunStatus.FAILED.value,
                    request_payload=payload_json,
                    response_summary=None,
                    error_message="The attached credential is unavailable or revoked.",
                    execution_time_ms=0,
                )

        mode = "REAL" if use_real else "SIMULATED"
        start = time.monotonic()
        try:
            if use_real:
                summary = await tool_connectors.execute_real(
                    tool.provider, normalized, secret, payload
                )
            else:
                summary = execute_readonly(tool.provider, normalized, payload)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            run = await self.run_repo.create(
                organization_id=organization_id,
                agent_id=agent.id,
                tool_id=tool.id,
                action=normalized,
                status=AITeamToolRunStatus.COMPLETED.value,
                request_payload=payload_json,
                response_summary=summary,
                execution_time_ms=elapsed_ms,
            )
            status_label = "success"
        except Exception as exc:  # noqa: BLE001 - normalize to customer-safe error
            elapsed_ms = int((time.monotonic() - start) * 1000)
            safe_msg = (
                str(exc)
                if isinstance(exc, ConnectorError)
                else "The tool could not complete the request."
            )
            run = await self.run_repo.create(
                organization_id=organization_id,
                agent_id=agent.id,
                tool_id=tool.id,
                action=normalized,
                status=AITeamToolRunStatus.FAILED.value,
                request_payload=payload_json,
                response_summary=None,
                error_message=safe_msg,
                execution_time_ms=elapsed_ms,
            )
            status_label = "failure"

        if use_real and credential is not None and secret_service is not None:
            await secret_service.record_usage(
                credential,
                user=current_user,
                org_context=org_context,
                deployment_id=run.id,
                reason="incident investigation",
            )
        await self.audit_repo.log(
            action="tool_executed" if status_label == "success" else "tool_execution_failed",
            resource_type="ai_team_tool",
            resource_id=tool.id,
            user_id=current_user.id,
            details={
                "tool_id": tool.id,
                "agent_id": agent.id,
                "run_id": run.id,
                "provider": tool.provider,
                "action": normalized,
                "mode": mode,
                "source": "incident_investigation",
            },
            status=status_label,
        )
        return run

    async def list_runs(
        self,
        tool_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamToolRunListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        tool = await self.tool_repo.get_for_org(tool_id, organization_id)
        if tool is None:
            raise NexoraException("Tool not found.", status_code=404)
        items, total = await self.run_repo.list_for_tool(
            tool.id, organization_id, offset=offset, limit=limit
        )
        return AITeamToolRunListResponse(
            items=[AITeamToolRunResponse.model_validate(r) for r in items], total=total
        )

    # ----------------------------------------- credentials (39C)
    async def _require_tool(self, tool_id: str, organization_id: str):
        tool = await self.tool_repo.get_for_org(tool_id, organization_id)
        if tool is None:
            raise NexoraException("Tool not found.", status_code=404)
        return tool

    async def attach_credential(
        self,
        tool_id: str,
        data: AITeamToolCredentialAttachRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamToolCredentialResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        tool = await self._require_tool(tool_id, organization_id)
        # Org-scoped credential lookup — cross-org or unknown is a 404.
        credential = await self.deployment_cred_repo.get_for_org(
            data.credential_id, organization_id
        )
        if credential is None:
            raise NexoraException("Credential not found.", status_code=404)
        if credential.provider != tool.provider:
            raise NexoraException(
                f"Credential provider ({credential.provider}) must match the tool "
                f"provider ({tool.provider}).",
                status_code=400,
            )
        existing = await self.cred_repo.get_mapping(
            tool.id, credential.id, organization_id
        )
        if existing is None:
            existing = await self.cred_repo.create(
                organization_id=organization_id,
                tool_id=tool.id,
                credential_id=credential.id,
            )
            await self.audit_repo.log(
                action="tool_credential_attached",
                resource_type="ai_team_tool",
                resource_id=tool.id,
                user_id=current_user.id,
                details={
                    "tool_id": tool.id,
                    "credential_id": credential.id,
                    "provider": tool.provider,
                },
            )
        return AITeamToolCredentialResponse(
            id=existing.id,
            organization_id=organization_id,
            tool_id=tool.id,
            credential_id=credential.id,
            provider=tool.provider,
            credential_name=credential.name,
            created_at=existing.created_at,
        )

    async def detach_credential(
        self,
        tool_id: str,
        credential_id: str,
        current_user: User,
        org_context: OrgContext,
    ) -> None:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        await self._require_tool(tool_id, organization_id)
        mapping = await self.cred_repo.get_mapping(
            tool_id, credential_id, organization_id
        )
        if mapping is None:
            raise NexoraException("Credential is not attached to this tool.", status_code=404)
        await self.cred_repo.hard_delete(mapping)
        await self.audit_repo.log(
            action="tool_credential_detached",
            resource_type="ai_team_tool",
            resource_id=tool_id,
            user_id=current_user.id,
            details={"tool_id": tool_id, "credential_id": credential_id},
        )

    async def connection_status(
        self, tool_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamToolConnectionStatusResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        tool = await self._require_tool(tool_id, organization_id)
        supports_real = provider_has_real_connector(tool.provider)
        mapping = await self.cred_repo.get_active_for_tool(tool.id, organization_id)
        credential_name = None
        credential_id = None
        if mapping is not None:
            credential_id = mapping.credential_id
            credential = await self.deployment_cred_repo.get_for_org(
                mapping.credential_id, organization_id
            )
            credential_name = credential.name if credential else None
        attached = mapping is not None
        mode = "REAL" if (attached and supports_real) else "SIMULATED"
        return AITeamToolConnectionStatusResponse(
            tool_id=tool.id,
            provider=tool.provider,
            attached=attached,
            mode=mode,
            supports_real_connection=supports_real,
            credential_id=credential_id,
            credential_name=credential_name,
        )

    async def verify_connection(
        self, tool_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamToolVerifyResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        tool = await self._require_tool(tool_id, organization_id)
        mapping = await self.cred_repo.get_active_for_tool(tool.id, organization_id)
        if mapping is None:
            raise NexoraException(
                "No credential is attached to this tool.", status_code=400
            )
        if not provider_has_real_connector(tool.provider):
            raise NexoraException(
                f"{tool.provider} does not support live verification yet.",
                status_code=400,
            )

        from app.security.secrets import SecretManagerService

        secret_service = SecretManagerService(self.session)
        # resolve_secret audits SECRET_USED and enforces org scope + active state.
        try:
            _credential, secret = await secret_service.resolve_secret(
                mapping.credential_id,
                user=current_user,
                org_context=org_context,
                reason="ai team tool connection verification",
                audit=True,
            )
        except NexoraException:
            await self.session.commit()
            return AITeamToolVerifyResponse(
                connected=False,
                provider=tool.provider,
                details={},
                error="The attached credential is unavailable or revoked.",
            )

        connected = False
        details: dict = {}
        error = None
        try:
            result = await tool_connectors.verify_connection(tool.provider, secret)
            connected = True
            details = result.get("details", {})
        except ConnectorError as exc:
            error = str(exc)
        except Exception:  # noqa: BLE001
            error = "Could not verify the connection with the provided credentials."

        await self.audit_repo.log(
            action="tool_connection_verified",
            resource_type="ai_team_tool",
            resource_id=tool.id,
            user_id=current_user.id,
            details={
                "tool_id": tool.id,
                "provider": tool.provider,
                "connected": connected,
            },
            status="success" if connected else "failure",
        )
        await self.session.commit()
        return AITeamToolVerifyResponse(
            connected=connected, provider=tool.provider, details=details, error=error
        )
