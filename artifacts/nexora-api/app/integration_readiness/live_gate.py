"""Centralized live mutation preflight gate (Sprint 65H)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NexoraException
from app.integration_readiness.capabilities import check_capability
from app.integration_readiness.evidence import build_live_evidence
from app.integration_readiness.preflight import make_idempotency_key, preflight_live_operation
from app.models.integration_readiness import IntConnectionRegistry, IntLiveEvidence
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.integration_readiness import IntRegistryRepo

# Map dotted capability names to registry matrix keys.
CAPABILITY_ALIASES: dict[str, str] = {
    "kubernetes.read": "read",
    "kubernetes.workloads.write": "write",
    "kubernetes.pods.delete": "write",
    "kubernetes.namespaces.write": "write",
    "kubernetes.storage.expand": "write",
    "kubernetes.networkpolicies.write": "write",
    "kubernetes.nodes.drain": "write",
    "cloud.resources.write": "write",
    "source.repositories.read": "read",
    "pipelines.read": "read",
    "deployment.execute": "deploy",
    "gitops.sync": "sync_gitops",
    "rollout.promote": "traffic_shift",
    "rollout.rollback": "write",
    "artifact.write": "write",
    "observability.metrics.query": "query_metrics",
    "observability.logs.query": "query_logs",
    "observability.traces.query": "query_traces",
    "iac.plan": "read",
    "iac.apply": "apply",
    "iac.destroy": "write",
    "cloud.provision": "write",
    "kubernetes.cluster.create": "write",
    "secrets.reference.read": "read",
    "enterprise.incidents.write": "write",
    "enterprise.issues.write": "write",
    "enterprise.alerts.write": "write",
    "enterprise.search.write": "write",
}

CONTROL_PLANE_CAPABILITIES: dict[str, list[str]] = {
    "scale_deployment": ["kubernetes.workloads.write"],
    "restart_deployment": ["kubernetes.workloads.write"],
    "rollout_restart": ["kubernetes.workloads.write"],
    "rollback_deployment": ["kubernetes.workloads.write"],
    "pause_rollout": ["kubernetes.workloads.write"],
    "resume_rollout": ["kubernetes.workloads.write"],
    "update_image": ["kubernetes.workloads.write"],
    "update_resources": ["kubernetes.workloads.write"],
    "delete_pod": ["kubernetes.pods.delete"],
    "restart_pod": ["kubernetes.pods.delete"],
    "evict_pod": ["kubernetes.pods.delete"],
    "cordon_node": ["kubernetes.nodes.drain"],
    "uncordon_node": ["kubernetes.nodes.drain"],
    "drain_node": ["kubernetes.nodes.drain"],
    "maintenance_node": ["kubernetes.nodes.drain"],
    "create_namespace": ["kubernetes.namespaces.write"],
    "delete_namespace": ["kubernetes.namespaces.write"],
    "expand_pvc": ["kubernetes.storage.expand"],
    "apply_network_policy": ["kubernetes.networkpolicies.write"],
}

DELIVERY_CAPABILITIES: dict[str, list[str]] = {
    "DEPLOY": ["deployment.execute"],
    "PROMOTE": ["rollout.promote", "deployment.execute"],
    "ROLLBACK": ["rollout.rollback"],
    "GITOPS_SYNC": ["gitops.sync"],
    "GITOPS_ROLLBACK": ["gitops.sync", "rollout.rollback"],
    "CANARY_SHIFT": ["rollout.promote"],
}

IAC_CAPABILITIES: dict[str, list[str]] = {
    "APPLY": ["iac.apply"],
    "IMPORT": ["iac.apply"],
    "DESTROY": ["iac.destroy"],
    "PLAN": ["iac.plan"],
}

ENTERPRISE_MUTATION_CAPABILITIES: dict[str, list[str]] = {
    "acknowledge_incident": ["enterprise.incidents.write"],
    "resolve_issue": ["enterprise.issues.write"],
    "trigger_search": ["enterprise.search.write"],
    "add_comment": ["enterprise.issues.write"],
    "acknowledge_alert": ["enterprise.alerts.write"],
}

REASON_CODES = {
    "disabled": "INTEGRATION_READINESS_DISABLED",
    "maintenance": "MAINTENANCE_MODE",
    "not_found": "CONNECTION_NOT_FOUND",
    "wrong_org": "ORGANIZATION_MISMATCH",
    "not_connected": "LIFECYCLE_NOT_CONNECTED",
    "not_live": "PROVIDER_NOT_LIVE",
    "no_credential": "CREDENTIAL_MISSING",
    "reauth": "REAUTH_REQUIRED",
    "expired": "CREDENTIAL_EXPIRED",
    "stale_validation": "VALIDATION_STALE",
    "missing_capability": "CAPABILITY_MISSING",
    "approval": "APPROVAL_REQUIRED",
    "no_idempotency": "IDEMPOTENCY_KEY_MISSING",
}


def normalize_capabilities(required: list[str]) -> list[str]:
    return [CAPABILITY_ALIASES.get(c, c) for c in required]


def missing_capabilities(capabilities: dict, required: list[str]) -> list[str]:
    missing: list[str] = []
    for cap in required:
        key = CAPABILITY_ALIASES.get(cap, cap)
        if not check_capability(capabilities, key):
            missing.append(cap)
    return missing


def build_readiness_context(
    *,
    registry: IntConnectionRegistry | None,
    result: dict,
    required_capabilities: list[str],
) -> dict[str, Any]:
    caps = (registry.capabilities or {}) if registry else {}
    missing = missing_capabilities(caps, required_capabilities) if registry else required_capabilities
    return {
        "connection_id": registry.id if registry else None,
        "state": registry.lifecycle_state if registry else None,
        "provider_mode": registry.provider_mode if registry else None,
        "last_validated_at": registry.last_validated_at.isoformat() if registry and registry.last_validated_at else None,
        "required_capabilities": required_capabilities,
        "missing_capabilities": missing,
        "preflight_status": "passed" if result.get("allowed") else "blocked",
        "blocked_reason": result.get("reason_code") or result.get("reason"),
        "remediation_guidance": result.get("remediation"),
        "correlation_id": result.get("correlation_id"),
        "simulated": result.get("simulated", False),
    }


class LiveMutationGate:
    """Mandatory preflight gate for all live infrastructure mutations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.registry = IntRegistryRepo(session)
        self.audit = AuditLogRepository(session)

    async def preflight_mutation(
        self,
        *,
        organization_id: str,
        actor_id: str | None,
        integration_connection_id: str | None,
        operation_type: str,
        resource_type: str,
        resource_id: str,
        environment_id: str | None = None,
        idempotency_key: str | None = None,
        required_capabilities: list[str],
        approval_satisfied: bool = True,
        explicit_simulation: bool = False,
        proposal_id: str | None = None,
        credential_id: str | None = None,
        resource_lookup: tuple[str, str] | None = None,
        destroy: bool = False,
    ) -> dict[str, Any]:
        correlation_id = idempotency_key or make_idempotency_key(
            org_id=organization_id, operation=operation_type, target_id=resource_id,
        )
        required = list(required_capabilities)

        await emit_event(
            self.session, DomainEventType.LIVE_OPERATION_PREFLIGHT_STARTED,
            organization_id=organization_id,
            payload={"operation_type": operation_type, "resource_id": resource_id, "correlation_id": correlation_id},
        )

        if not getattr(settings, "INTEGRATION_READINESS_ENABLED", True):
            return self._simulation_only_result(
                correlation_id, reason_code=REASON_CODES["disabled"],
                remediation="Integration readiness is disabled; only explicit simulation is permitted.",
                explicit_simulation=explicit_simulation,
            )

        if getattr(settings, "MAINTENANCE_MODE_ENABLED", False) and not explicit_simulation:
            return await self._blocked(
                organization_id=organization_id,
                actor_id=actor_id,
                registry=None,
                operation_type=operation_type,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                reason="Maintenance mode is active",
                reason_code=REASON_CODES["maintenance"],
                remediation="Retry after maintenance completes or use explicit simulation in non-production.",
                required_capabilities=required,
                proposal_id=proposal_id,
            )

        if not correlation_id:
            return await self._blocked(
                organization_id=organization_id,
                actor_id=actor_id,
                registry=None,
                operation_type=operation_type,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id or "missing",
                reason="Idempotency key is required",
                reason_code=REASON_CODES["no_idempotency"],
                remediation="Provide a stable idempotency key for this operation.",
                required_capabilities=required,
                proposal_id=proposal_id,
            )

        row = await self._resolve_registry(
            organization_id,
            integration_connection_id=integration_connection_id,
            credential_id=credential_id,
            resource_lookup=resource_lookup,
        )
        if row is None:
            if explicit_simulation:
                return self._simulation_only_result(correlation_id, explicit_simulation=True)
            return await self._blocked(
                organization_id=organization_id,
                actor_id=actor_id,
                registry=None,
                operation_type=operation_type,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                reason="No integration readiness record found for this connection",
                reason_code=REASON_CODES["not_found"],
                remediation="Connect and validate the integration, then retry.",
                required_capabilities=required,
                proposal_id=proposal_id,
            )

        if row.organization_id != organization_id:
            return await self._blocked(
                organization_id=organization_id,
                actor_id=actor_id,
                registry=row,
                operation_type=operation_type,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                reason="Integration does not belong to this organization",
                reason_code=REASON_CODES["wrong_org"],
                remediation="Switch to the correct organization context.",
                required_capabilities=required,
                proposal_id=proposal_id,
            )

        freshness_hours = getattr(
            settings, "INTEGRATION_DESTROY_FRESHNESS_HOURS" if destroy else "INTEGRATION_VALIDATION_FRESHNESS_HOURS",
            4 if destroy else 24,
        )
        stale = self._validation_stale(row, freshness_hours)
        registry_dict = {
            "organization_id": row.organization_id,
            "lifecycle_state": row.lifecycle_state,
            "provider_mode": row.provider_mode,
            "capabilities": row.capabilities,
            "credential_id": row.credential_id,
            "reauth_required": row.reauth_required,
        }

        if stale and not explicit_simulation:
            return await self._blocked(
                organization_id=organization_id,
                actor_id=actor_id,
                registry=row,
                operation_type=operation_type,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                reason=f"Last validation is older than {freshness_hours}h",
                reason_code=REASON_CODES["stale_validation"],
                remediation="Re-validate the integration connection before executing live mutations.",
                required_capabilities=required,
                proposal_id=proposal_id,
            )

        normalized = normalize_capabilities(required)
        result = preflight_live_operation(
            registry=registry_dict,
            required_capabilities=normalized,
            environment_id=environment_id,
            organization_id=organization_id,
            idempotency_key=correlation_id,
            approval_satisfied=approval_satisfied,
            explicit_simulation=explicit_simulation,
        )

        if not result["allowed"] and not explicit_simulation:
            reason_code = self._reason_code_for(result.get("reason", ""))
            return await self._blocked(
                organization_id=organization_id,
                actor_id=actor_id,
                registry=row,
                operation_type=operation_type,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                reason=result.get("reason") or "Preflight blocked",
                reason_code=reason_code,
                remediation=result.get("remediation"),
                required_capabilities=required,
                proposal_id=proposal_id,
            )

        await self._persist_evidence(
            organization_id=organization_id,
            registry_id=row.id,
            operation_type=operation_type,
            operation_id=resource_id,
            correlation_id=correlation_id,
            outcome="allowed",
            result=result,
            resource_type=resource_type,
            required_capabilities=required,
            registry=row,
        )
        await emit_event(
            self.session, DomainEventType.LIVE_OPERATION_PREFLIGHT_PASSED,
            organization_id=organization_id,
            payload={"correlation_id": correlation_id, "simulated": result.get("simulated", False)},
        )
        await self.audit.log(
            action="live_operation.preflight_passed",
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=actor_id,
            organization_id=organization_id,
            details={"correlation_id": correlation_id, "simulated": result.get("simulated")},
        )
        self._record_metrics("passed", operation_type)
        return {
            "allowed": True,
            "simulated": result.get("simulated", False),
            "connection_id": row.id,
            "provider_mode": row.provider_mode if not result.get("simulated") else "offline",
            "validated_capabilities": {k: v for k, v in (row.capabilities or {}).items() if v},
            "correlation_id": correlation_id,
            "evidence_context": build_readiness_context(registry=row, result=result, required_capabilities=required),
            "lifecycle_state": row.lifecycle_state,
            "remediation": None,
            "reason": None,
            "reason_code": None,
        }

    async def record_execution(
        self,
        *,
        organization_id: str,
        actor_id: str | None,
        connection_id: str | None,
        operation_type: str,
        resource_id: str,
        correlation_id: str,
        outcome: str,
        result_summary: dict | None = None,
        verification: dict | None = None,
        provider_correlation_id: str | None = None,
    ) -> None:
        event_map = {
            "started": DomainEventType.LIVE_OPERATION_EXECUTION_STARTED,
            "succeeded": DomainEventType.LIVE_OPERATION_EXECUTION_SUCCEEDED,
            "failed": DomainEventType.LIVE_OPERATION_EXECUTION_FAILED,
        }
        if outcome in event_map:
            await emit_event(
                self.session, event_map[outcome],
                organization_id=organization_id,
                payload={"correlation_id": correlation_id, "resource_id": resource_id},
            )
        if verification and not verification.get("verified"):
            await emit_event(
                self.session, DomainEventType.LIVE_OPERATION_VERIFICATION_FAILED,
                organization_id=organization_id,
                payload={"correlation_id": correlation_id, "resource_id": resource_id},
            )
        ev = IntLiveEvidence(
            organization_id=organization_id,
            registry_id=connection_id,
            operation_type=operation_type,
            operation_id=resource_id,
            correlation_id=correlation_id,
            outcome=outcome,
            evidence=build_live_evidence(
                correlation_id=provider_correlation_id or correlation_id,
                resource_ids={"operation_id": resource_id},
                outcome=outcome,
                post_state=result_summary or {},
                log_snippet=str((result_summary or {}).get("message", ""))[:500],
            ),
            verification=verification or {},
        )
        self.session.add(ev)
        await self.audit.log(
            action=f"live_operation.execution_{outcome}",
            resource_type="live_mutation",
            resource_id=resource_id,
            user_id=actor_id,
            organization_id=organization_id,
            details={"correlation_id": correlation_id, "outcome": outcome},
        )
        self._record_metrics(outcome, operation_type, execution=True)

    async def _resolve_registry(
        self,
        organization_id: str,
        *,
        integration_connection_id: str | None,
        credential_id: str | None,
        resource_lookup: tuple[str, str] | None,
    ) -> IntConnectionRegistry | None:
        if integration_connection_id:
            row = await self.registry.get_by_id(integration_connection_id)
            if row and row.organization_id == organization_id:
                return row
        if resource_lookup:
            row = await self.registry.get_by_resource(organization_id, resource_lookup[0], resource_lookup[1])
            if row:
                return row
        if credential_id:
            rows = await self.registry.list_for_org(organization_id)
            for row in rows:
                if row.credential_id == credential_id:
                    return row
        return None

    async def ensure_registry(
        self,
        *,
        organization_id: str,
        resource_type: str,
        resource_id: str,
        provider_type: str,
        credential_id: str | None,
    ) -> IntConnectionRegistry:
        existing = await self.registry.get_by_resource(organization_id, resource_type, resource_id)
        if existing:
            return existing
        key = make_idempotency_key(org_id=organization_id, operation=resource_type, target_id=resource_id)
        row = IntConnectionRegistry(
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            provider_type=provider_type.upper(),
            credential_id=credential_id,
            lifecycle_state="DRAFT",
            provider_mode="unavailable",
            capabilities={},
            idempotency_key=key,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    @staticmethod
    def _validation_stale(row: IntConnectionRegistry, max_hours: int) -> bool:
        if not row.last_validated_at:
            return True
        validated = row.last_validated_at
        if validated.tzinfo is None:
            validated = validated.replace(tzinfo=UTC)
        age = datetime.now(UTC) - validated
        return age > timedelta(hours=max_hours)

    @staticmethod
    def _reason_code_for(reason: str) -> str:
        lower = reason.lower()
        if "connected" in lower:
            return REASON_CODES["not_connected"]
        if "live" in lower and "mode" in lower:
            return REASON_CODES["not_live"]
        if "credential" in lower and "reference" in lower:
            return REASON_CODES["no_credential"]
        if "reauth" in lower:
            return REASON_CODES["reauth"]
        if "expired" in lower:
            return REASON_CODES["expired"]
        if "approval" in lower:
            return REASON_CODES["approval"]
        if "capability" in lower:
            return REASON_CODES["missing_capability"]
        if "organization" in lower:
            return REASON_CODES["wrong_org"]
        return "PREFLIGHT_BLOCKED"

    async def _blocked(
        self,
        *,
        organization_id: str,
        actor_id: str | None,
        registry: IntConnectionRegistry | None,
        operation_type: str,
        resource_type: str,
        resource_id: str,
        correlation_id: str,
        reason: str,
        reason_code: str,
        remediation: str | None,
        required_capabilities: list[str],
        proposal_id: str | None,
    ) -> dict[str, Any]:
        result = {
            "allowed": False,
            "simulated": False,
            "reason": reason,
            "reason_code": reason_code,
            "remediation": remediation,
            "correlation_id": correlation_id,
            "missing_capabilities": missing_capabilities(registry.capabilities or {}, required_capabilities) if registry else required_capabilities,
            "lifecycle_state": registry.lifecycle_state if registry else None,
            "provider_mode": registry.provider_mode if registry else None,
            "connection_id": registry.id if registry else None,
            "evidence_context": build_readiness_context(
                registry=registry,
                result={"allowed": False, "reason_code": reason_code, "remediation": remediation, "correlation_id": correlation_id},
                required_capabilities=required_capabilities,
            ),
        }
        await self._persist_evidence(
            organization_id=organization_id,
            registry_id=registry.id if registry else None,
            operation_type=operation_type,
            operation_id=resource_id,
            correlation_id=correlation_id,
            outcome="blocked",
            result=result,
            resource_type=resource_type,
            required_capabilities=required_capabilities,
            registry=registry,
            blocked_reason=reason,
        )
        await emit_event(
            self.session, DomainEventType.LIVE_OPERATION_PREFLIGHT_BLOCKED,
            organization_id=organization_id,
            payload={"correlation_id": correlation_id, "reason_code": reason_code, "proposal_id": proposal_id},
        )
        await self.audit.log(
            action="live_operation.preflight_blocked",
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=actor_id,
            organization_id=organization_id,
            details={"reason_code": reason_code, "correlation_id": correlation_id},
        )
        self._record_metrics("blocked", operation_type, reason_code=reason_code)
        return result

    async def _persist_evidence(
        self,
        *,
        organization_id: str,
        registry_id: str | None,
        operation_type: str,
        operation_id: str,
        correlation_id: str,
        outcome: str,
        result: dict,
        resource_type: str,
        required_capabilities: list[str],
        registry: IntConnectionRegistry | None,
        blocked_reason: str | None = None,
    ) -> None:
        ev = IntLiveEvidence(
            organization_id=organization_id,
            registry_id=registry_id,
            operation_type=operation_type,
            operation_id=operation_id,
            correlation_id=correlation_id,
            outcome=outcome,
            blocked_reason=blocked_reason,
            evidence=build_live_evidence(
                correlation_id=correlation_id,
                resource_ids={"resource_type": resource_type, "resource_id": operation_id},
                outcome=outcome,
                pre_state={
                    "lifecycle_state": registry.lifecycle_state if registry else None,
                    "provider_mode": registry.provider_mode if registry else None,
                    "required_capabilities": required_capabilities,
                    "missing_capabilities": result.get("missing_capabilities", []),
                },
            ),
            verification={"simulated": result.get("simulated", False), "reason_code": result.get("reason_code")},
        )
        self.session.add(ev)

    @staticmethod
    def _simulation_only_result(
        correlation_id: str,
        *,
        explicit_simulation: bool,
        reason_code: str | None = None,
        remediation: str | None = None,
    ) -> dict[str, Any]:
        if not explicit_simulation:
            return {
                "allowed": False,
                "simulated": False,
                "reason": remediation or "Explicit simulation required",
                "reason_code": reason_code or "SIMULATION_REQUIRED",
                "remediation": remediation,
                "correlation_id": correlation_id,
            }
        return {
            "allowed": True,
            "simulated": True,
            "connection_id": None,
            "provider_mode": "offline",
            "validated_capabilities": {},
            "correlation_id": correlation_id,
            "evidence_context": {"preflight_status": "passed", "simulated": True},
            "lifecycle_state": None,
            "remediation": None,
            "reason": None,
            "reason_code": None,
        }

    @staticmethod
    def _record_metrics(outcome: str, operation_type: str, *, execution: bool = False, reason_code: str | None = None) -> None:
        try:
            from app.observability import metrics
            if execution:
                metrics.record_live_operation_execution(outcome, operation_type)
            else:
                metrics.record_live_preflight(outcome, operation_type, reason_code=reason_code)
        except Exception:  # pragma: no cover
            pass


def require_preflight_or_raise(result: dict) -> dict:
    """Raise structured error when preflight blocks a live mutation."""
    if result.get("allowed"):
        return result
    raise NexoraException(
        result.get("reason") or "Live operation blocked by integration preflight",
        400,
        details={
            "integration_readiness": result.get("evidence_context"),
            "reason_code": result.get("reason_code"),
            "remediation": result.get("remediation"),
            "correlation_id": result.get("correlation_id"),
        },
    )
