"""Enterprise connector mutations behind LiveMutationGate (P0 production gate)."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import NotFoundError
from app.integration_readiness.live_gate import (
    ENTERPRISE_MUTATION_CAPABILITIES,
    LiveMutationGate,
    require_preflight_or_raise,
)
from app.integration_readiness.preflight import make_idempotency_key
from app.models.user import User
from app.repositories.integration import IntegrationConnectionRepository
from app.security.secrets import SecretManagerService
from app.services.enterprise_enrichment import mutate_provider
from app.services.integration_readiness import IntegrationReadinessService

ENTERPRISE_KEYS = frozenset({"SERVICENOW", "SPLUNK", "SENTRY", "PAGERDUTY", "JIRA", "OPSGENIE"})


class EnterpriseMutationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.connections = IntegrationConnectionRepository(session)
        self.secrets = SecretManagerService(session)
        self.readiness = IntegrationReadinessService(session)

    async def mutate(
        self,
        *,
        user: User,
        org_context: OrgContext,
        connection_id: str,
        action: str,
        resource_id: str,
        note: str = "",
        explicit_simulation: bool = False,
        idempotency_key: str | None = None,
    ) -> dict:
        organization_id = org_context.requires_organization
        conn = await self.connections.get_for_org(connection_id, organization_id)
        if not conn:
            raise NotFoundError("IntegrationConnection", connection_id)

        key = (conn.integration_key or "").upper()
        if key not in ENTERPRISE_KEYS:
            return {"status": "failed", "reason": "not_enterprise_connector"}

        required = ENTERPRISE_MUTATION_CAPABILITIES.get(action)
        if not required:
            return {"status": "failed", "reason": f"unsupported_action:{action}"}

        if not conn.credential_id:
            return {"status": "failed", "reason": "no_credential"}

        await self.readiness.sync_registry(organization_id)
        gate = LiveMutationGate(self.session)
        correlation_id = idempotency_key or make_idempotency_key(
            org_id=organization_id,
            operation=f"enterprise.{action}",
            target_id=resource_id,
        )
        preflight = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=None,
            operation_type=f"enterprise.{action}",
            resource_type="marketplace",
            resource_id=connection_id,
            idempotency_key=correlation_id,
            required_capabilities=required,
            approval_satisfied=True,
            explicit_simulation=explicit_simulation,
            credential_id=conn.credential_id,
            resource_lookup=("marketplace", connection_id),
        )
        require_preflight_or_raise(preflight)

        await gate.record_execution(
            organization_id=organization_id,
            actor_id=user.id,
            connection_id=preflight.get("connection_id"),
            operation_type=f"enterprise.{action}",
            resource_id=resource_id,
            correlation_id=correlation_id,
            outcome="started",
        )

        if preflight.get("simulated"):
            result = {
                "status": "simulated",
                "action": action,
                "resource_id": resource_id,
                "message": f"Simulated {action} (no live provider call)",
            }
        else:
            _, secret = await self.secrets.resolve_secret(
                conn.credential_id,
                user=user,
                org_context=org_context,
                reason=f"integration mutate:{action}",
            )
            result = await asyncio.to_thread(
                mutate_provider,
                key,
                secret,
                action,
                resource_id,
                note=note,
            )

        outcome = "succeeded" if result.get("status") not in ("failed",) else "failed"
        await gate.record_execution(
            organization_id=organization_id,
            actor_id=user.id,
            connection_id=preflight.get("connection_id"),
            operation_type=f"enterprise.{action}",
            resource_id=resource_id,
            correlation_id=correlation_id,
            outcome=outcome,
            result_summary=result,
        )
        return {
            **result,
            "correlation_id": correlation_id,
            "simulated": preflight.get("simulated", False),
            "integration_readiness": preflight.get("evidence_context"),
        }
