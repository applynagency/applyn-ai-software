"""Customer integration onboarding service (Sprint 67A).

Onboarding and validation only — no pilot enrollments, operations, approvals,
stage transitions, or provider mutations.
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.integration_onboarding.rbac_templates import build_rbac_role_yaml, least_privilege_guidance
from app.integration_onboarding.scope import (
    validate_environment_classification,
    validate_kubernetes_scope,
    validate_prometheus_scope,
    validate_source_scope,
)
from app.integration_onboarding.validators import (
    validate_kubernetes,
    validate_prometheus,
    validate_source_control,
)
from app.integration_readiness.capabilities import build_capability_matrix
from app.integration_readiness.evidence import redact_text
from app.models.integration_onboarding import ONBOARDING_PROVIDERS, IntegrationOnboardingSession
from app.models.integration_readiness import IntConnectionRegistry
from app.models.pilot import PilotEnrollment, PilotLiveOperation, PilotStage
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.integration_onboarding import IntegrationOnboardingRepo
from app.repositories.integration_readiness import IntRegistryRepo
from app.security.secrets import SecretManagerService
from app.services.integration_verification import VStatus
from app.tenancy.permissions import can_manage_organization, can_read_resources

_PROVIDER_CATALOG = [
    {
        "provider_type": "KUBERNETES",
        "display_name": "Kubernetes",
        "description": "Non-production namespace-scoped cluster access for read-only assessment",
        "required_scope_fields": ["namespace", "cluster_endpoint"],
    },
    {
        "provider_type": "GITHUB",
        "display_name": "GitHub",
        "description": "Read-only access to a single repository",
        "required_scope_fields": ["repository"],
    },
    {
        "provider_type": "GITHUB_ENTERPRISE",
        "display_name": "GitHub Enterprise",
        "description": "Read-only access to a single repository via enterprise API URL",
        "required_scope_fields": ["repository", "api_base_url"],
    },
    {
        "provider_type": "GITEA",
        "display_name": "Gitea",
        "description": "Gitea-compatible read-only repository access",
        "required_scope_fields": ["repository", "api_base_url"],
    },
    {
        "provider_type": "PROMETHEUS",
        "display_name": "Prometheus",
        "description": "Read-only Prometheus-compatible metrics queries",
        "required_scope_fields": ["namespace_label", "namespace_label_value"],
    },
]


def _idempotency_key(org_id: str, session_id: str) -> str:
    raw = f"onboarding:{org_id}:{session_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _credential_provider(provider_type: str) -> str:
    if provider_type == "KUBERNETES":
        return "KUBERNETES"
    if provider_type in ("GITHUB", "GITHUB_ENTERPRISE", "GITEA"):
        return "GITHUB"
    if provider_type == "PROMETHEUS":
        return "PROMETHEUS"
    return provider_type


def _resource_type(provider_type: str) -> str:
    return "observability" if provider_type == "PROMETHEUS" else "marketplace"


class IntegrationOnboardingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IntegrationOnboardingRepo(session)
        self.registry = IntRegistryRepo(session)
        self.secrets = SecretManagerService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_admin(self, user: User, org_context: OrgContext) -> str:
        if not can_manage_organization(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Organization admin permissions required for integration onboarding")
        return org_context.requires_organization

    def list_providers(self) -> list[dict]:
        return _PROVIDER_CATALOG

    async def create_session(
        self, user: User, org_context: OrgContext, *, provider_type: str, intended_for_pilot: bool = True,
    ) -> IntegrationOnboardingSession:
        organization_id = self._ensure_admin(user, org_context)
        ptype = provider_type.upper()
        if ptype not in ONBOARDING_PROVIDERS:
            raise ValidationError(f"Unsupported provider type: {provider_type}")

        row = IntegrationOnboardingSession(
            organization_id=organization_id,
            provider_type=ptype,
            status="DRAFT",
            intended_for_pilot=intended_for_pilot,
            owner_user_id=user.id,
            scope={},
            validation_summary={},
            evidence_refs={},
            required_capabilities=[],
            missing_capabilities=[],
        )
        self.session.add(row)
        await self.session.flush()

        await emit_event(
            self.session, DomainEventType.INTEGRATION_ONBOARDING_STARTED,
            organization_id=organization_id,
            payload={"session_id": row.id, "provider_type": ptype},
        )
        self._record_session_metric("created", ptype)
        await self.audit.log(
            action="onboarding.integration.session_created",
            resource_type="int_onboarding_session",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"provider_type": ptype, "intended_for_pilot": intended_for_pilot},
        )
        return row

    async def list_sessions(self, user: User, org_context: OrgContext) -> list[IntegrationOnboardingSession]:
        organization_id = self._ensure_read(user, org_context)
        return await self.repo.list_for_org(organization_id)

    async def get_session(
        self, user: User, org_context: OrgContext, session_id: str,
    ) -> IntegrationOnboardingSession:
        organization_id = self._ensure_read(user, org_context)
        row = await self.repo.get_for_org(session_id, organization_id)
        if not row:
            raise NotFoundError("IntegrationOnboardingSession", session_id)
        return row

    async def update_environment(
        self,
        user: User,
        org_context: OrgContext,
        session_id: str,
        *,
        environment_name: str,
        environment_classification: str,
        scope: dict,
        intended_for_pilot: bool,
        api_base_url: str | None = None,
    ) -> IntegrationOnboardingSession:
        organization_id = self._ensure_admin(user, org_context)
        row = await self.get_session(user, org_context, session_id)
        if row.status in ("CANCELLED", "READY_FOR_PILOT"):
            raise ValidationError(f"Session cannot be updated in status {row.status}")

        try:
            validate_environment_classification(environment_classification, intended_for_pilot=intended_for_pilot)
            if row.provider_type == "KUBERNETES":
                validate_kubernetes_scope(scope)
            elif row.provider_type in ("GITHUB", "GITHUB_ENTERPRISE", "GITEA"):
                validate_source_scope(scope)
            elif row.provider_type == "PROMETHEUS":
                validate_prometheus_scope(scope)
        except ValidationError as exc:
            await emit_event(
                self.session, DomainEventType.INTEGRATION_SCOPE_REJECTED,
                organization_id=organization_id,
                payload={"session_id": session_id, "reason": str(exc)},
            )
            self._record_rbac_gap(row.provider_type, "scope_rejected")
            raise

        row.environment_name = environment_name.strip()
        row.environment_classification = environment_classification.strip().lower()
        row.scope = scope or {}
        row.intended_for_pilot = intended_for_pilot
        row.api_base_url = api_base_url.rstrip("/") if api_base_url else row.api_base_url
        await self.session.flush()
        return row

    async def store_credentials(
        self,
        user: User,
        org_context: OrgContext,
        session_id: str,
        *,
        name: str,
        secret: dict,
    ) -> IntegrationOnboardingSession:
        organization_id = self._ensure_admin(user, org_context)
        row = await self.get_session(user, org_context, session_id)
        if row.status in ("CANCELLED", "READY_FOR_PILOT", "VALIDATING"):
            raise ValidationError(f"Credentials cannot be stored in status {row.status}")
        if not row.environment_name:
            raise ValidationError("Configure environment and scope before storing credentials")

        cred = await self.secrets.create_credential(
            provider=_credential_provider(row.provider_type),
            name=name or f"onboarding-{row.provider_type.lower()}",
            secret=secret,
            user=user,
            org_context=org_context,
        )
        row.credential_id = cred.id
        row.status = "CREDENTIALS_ADDED"
        await self.session.flush()

        await emit_event(
            self.session, DomainEventType.INTEGRATION_CREDENTIAL_STORED,
            organization_id=organization_id,
            payload={"session_id": session_id, "credential_id": cred.id, "provider_type": row.provider_type},
        )
        await self.audit.log(
            action="onboarding.integration.credential_stored",
            resource_type="int_onboarding_session",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"credential_id": cred.id, "provider_type": row.provider_type},
        )
        return row

    async def validate_session(
        self, user: User, org_context: OrgContext, session_id: str,
    ) -> dict:
        organization_id = self._ensure_admin(user, org_context)
        row = await self.get_session(user, org_context, session_id)
        if not row.credential_id:
            raise ValidationError("Credentials must be stored before validation")
        if row.status == "CANCELLED":
            raise ValidationError("Session is cancelled")

        row.status = "VALIDATING"
        await self.session.flush()

        await emit_event(
            self.session, DomainEventType.INTEGRATION_VALIDATION_STARTED,
            organization_id=organization_id,
            payload={"session_id": session_id, "provider_type": row.provider_type, "onboarding": True},
        )
        self._record_validation_metric(row.provider_type, "started")

        started = time.monotonic()
        _, secret = await self.secrets.resolve_secret(
            row.credential_id,
            user=user,
            org_context=org_context,
            reason="onboarding_validate",
            audit=False,
        )

        result = await self._run_provider_validation(row, secret)
        duration = time.monotonic() - started

        row.validation_summary = {
            k: v for k, v in result.items()
            if k not in ("raw_secret",) and not str(k).startswith("_")
        }
        row.evidence_refs = result.get("evidence_refs") or {}
        row.missing_capabilities = result.get("missing_capabilities") or result.get("rbac_gaps") or []
        row.required_capabilities = list((result.get("capabilities") or {}).keys())

        ok = result.get("ok", False)
        prohibited = result.get("prohibited_granted") or []
        if prohibited:
            ok = False
            row.status = "FAILED"
            row.readiness_verdict = "NO_GO"
            await emit_event(
                self.session, DomainEventType.INTEGRATION_SCOPE_REJECTED,
                organization_id=organization_id,
                payload={"session_id": session_id, "prohibited": prohibited},
            )
            self._record_rbac_gap(row.provider_type, "prohibited_permission")
        elif result.get("connection_status") == VStatus.UNAUTHORIZED:
            row.status = "REAUTH_REQUIRED"
            row.readiness_verdict = "NO_GO"
        elif ok:
            row.status = "VALIDATED"
            insufficient = result.get("insufficient_evidence") or []
            row.readiness_verdict = "INSUFFICIENT_EVIDENCE" if insufficient else "GO"
            registry_id = await self._register_connection(row, result, organization_id)
            row.registry_connection_id = registry_id
            await emit_event(
                self.session, DomainEventType.INTEGRATION_VALIDATION_SUCCEEDED,
                organization_id=organization_id,
                payload={"session_id": session_id, "registry_id": registry_id, "onboarding": True},
            )
            self._record_validation_metric(row.provider_type, "succeeded")
        else:
            row.status = "FAILED"
            row.readiness_verdict = "NO_GO"
            await emit_event(
                self.session, DomainEventType.INTEGRATION_VALIDATION_FAILED,
                organization_id=organization_id,
                payload={"session_id": session_id, "onboarding": True},
            )
            self._record_validation_metric(row.provider_type, "failed")

        if result.get("rbac_gaps"):
            await emit_event(
                self.session, DomainEventType.INTEGRATION_RBAC_GAP_DETECTED,
                organization_id=organization_id,
                payload={"session_id": session_id, "gaps": result.get("rbac_gaps")},
            )
            for _ in result.get("rbac_gaps") or []:
                self._record_rbac_gap(row.provider_type, "gap")

        self._record_validation_duration(row.provider_type, duration)
        await self.audit.log(
            action="onboarding.integration.validated",
            resource_type="int_onboarding_session",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={
                "status": row.status,
                "readiness_verdict": row.readiness_verdict,
                "registry_connection_id": row.registry_connection_id,
            },
        )
        await self.session.flush()
        return {
            "session_id": row.id,
            "status": row.status,
            "validation_summary": row.validation_summary,
            "readiness_verdict": row.readiness_verdict,
            "registry_connection_id": row.registry_connection_id,
            "missing_capabilities": row.missing_capabilities,
            "evidence_refs": row.evidence_refs,
        }

    async def _run_provider_validation(self, row: IntegrationOnboardingSession, secret: dict) -> dict:
        if row.provider_type == "KUBERNETES":
            namespace = validate_kubernetes_scope(row.scope)
            return await validate_kubernetes(secret, namespace=namespace)
        if row.provider_type in ("GITHUB", "GITHUB_ENTERPRISE", "GITEA"):
            repository = validate_source_scope(row.scope)
            return await validate_source_control(
                row.provider_type, secret, repository=repository, api_base_url=row.api_base_url,
            )
        if row.provider_type == "PROMETHEUS":
            prom_scope = validate_prometheus_scope(row.scope)
            return await validate_prometheus(secret, scope=prom_scope)
        raise ValidationError(f"Validation not implemented for {row.provider_type}")

    async def _register_connection(
        self,
        row: IntegrationOnboardingSession,
        result: dict,
        organization_id: str,
    ) -> str | None:
        """Register CONNECTED+live registry row only after successful validation."""
        if not result.get("ok"):
            return None

        caps = result.get("capabilities") or {}
        permissions = [k for k, v in caps.items() if v]
        matrix = build_capability_matrix(row.provider_type, permissions)
        resource_id = row.id
        if row.provider_type == "KUBERNETES":
            resource_id = row.scope.get("cluster_endpoint") or row.scope.get("cluster_name") or row.id

        key = _idempotency_key(organization_id, row.id)
        existing = await self.registry.get_by_idempotency(organization_id, key)
        meta = {
            "onboarding_session_id": row.id,
            "environment_name": row.environment_name,
            "environment_classification": row.environment_classification,
            "scope": row.scope,
            "rbac_evidence": {
                "namespace_scoped": row.provider_type == "KUBERNETES",
                "summary": "Onboarding validation evidence (redacted)",
                "gaps": result.get("rbac_gaps") or [],
            },
            "provider_identity": result.get("provider_identity") or result.get("evidence_refs") or {},
            "warnings": result.get("warnings") or [],
        }

        if existing:
            existing.credential_id = row.credential_id
            existing.lifecycle_state = "CONNECTED"
            existing.provider_mode = result.get("provider_mode") or "live"
            existing.capabilities = matrix
            existing.validation_metadata = meta
            existing.last_validated_at = datetime.now(UTC)
            existing.last_successful_at = datetime.now(UTC)
            existing.failure_reason = None
            existing.reauth_required = False
            reg = existing
        else:
            reg = IntConnectionRegistry(
                organization_id=organization_id,
                resource_type=_resource_type(row.provider_type),
                resource_id=str(resource_id)[:36],
                provider_type=row.provider_type if row.provider_type != "GITHUB_ENTERPRISE" else "GITHUB",
                credential_id=row.credential_id,
                lifecycle_state="CONNECTED",
                provider_mode=result.get("provider_mode") or "live",
                capabilities=matrix,
                validation_metadata=meta,
                last_validated_at=datetime.now(UTC),
                last_successful_at=datetime.now(UTC),
                idempotency_key=key,
            )
            self.session.add(reg)

        await self.session.flush()
        return reg.id

    async def get_rbac_report(
        self, user: User, org_context: OrgContext, session_id: str,
    ) -> dict:
        row = await self.get_session(user, org_context, session_id)
        summary = row.validation_summary or {}
        inv = summary.get("inventory") or {}
        return {
            "session_id": row.id,
            "provider_type": row.provider_type,
            "rbac_gaps": summary.get("rbac_gaps") or row.missing_capabilities or [],
            "prohibited_granted": summary.get("prohibited_granted") or [],
            "read_checks": summary.get("read_checks") or [],
            "scale_checks": summary.get("scale_checks") or [],
            "inventory_summary": {
                "deployment_count": len(inv.get("deployments", [])),
                "pod_count": len(inv.get("pods", [])),
                "namespace": inv.get("namespace") or row.scope.get("namespace"),
            },
        }

    async def get_least_privilege_guide(
        self, user: User, org_context: OrgContext, session_id: str,
    ) -> dict:
        row = await self.get_session(user, org_context, session_id)
        ns = row.scope.get("namespace")
        guidance = least_privilege_guidance(provider=row.provider_type, namespace=ns)
        minimum_yaml = None
        optional_yaml = None
        if row.provider_type == "KUBERNETES" and ns:
            minimum_yaml = build_rbac_role_yaml(namespace=ns, include_scale=False)
            optional_yaml = build_rbac_role_yaml(namespace=ns, include_scale=True)
        return {
            "session_id": row.id,
            "provider_type": row.provider_type,
            "guidance": guidance,
            "minimum_rbac_yaml": minimum_yaml,
            "optional_scale_yaml": optional_yaml,
        }

    async def acknowledge(
        self, user: User, org_context: OrgContext, session_id: str, *, acknowledged: bool = True,
        acknowledgement_note: str | None = None,
    ) -> IntegrationOnboardingSession:
        organization_id = self._ensure_admin(user, org_context)
        row = await self.get_session(user, org_context, session_id)
        if row.status != "VALIDATED":
            raise ValidationError("Session must be validated before acknowledgement")
        if not acknowledged:
            raise ValidationError("Acknowledgement is required to mark onboarding ready for pilot")

        row.status = "READY_FOR_PILOT"
        row.acknowledged_at = datetime.now(UTC).isoformat()
        row.validation_summary = {
            **(row.validation_summary or {}),
            "acknowledgement_note": redact_text(acknowledgement_note or "")[:500],
        }
        await self.session.flush()

        await self.audit.log(
            action="onboarding.integration.acknowledged",
            resource_type="int_onboarding_session",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"registry_connection_id": row.registry_connection_id},
        )
        return row

    async def cancel(
        self, user: User, org_context: OrgContext, session_id: str, *, reason: str,
    ) -> IntegrationOnboardingSession:
        organization_id = self._ensure_admin(user, org_context)
        row = await self.get_session(user, org_context, session_id)
        row.status = "CANCELLED"
        row.cancellation_reason = redact_text(reason)[:1000]
        await self.session.flush()

        await emit_event(
            self.session, DomainEventType.INTEGRATION_ONBOARDING_CANCELLED,
            organization_id=organization_id,
            payload={"session_id": session_id, "reason": row.cancellation_reason},
        )
        await self.audit.log(
            action="onboarding.integration.cancelled",
            resource_type="int_onboarding_session",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"reason": row.cancellation_reason},
        )
        return row

    async def get_evidence(
        self, user: User, org_context: OrgContext, session_id: str,
    ) -> dict:
        row = await self.get_session(user, org_context, session_id)
        return {
            "session_id": row.id,
            "provider_type": row.provider_type,
            "status": row.status,
            "evidence_refs": row.evidence_refs,
            "validation_summary": {
                k: v for k, v in (row.validation_summary or {}).items()
                if k not in ("inventory",)
            },
            "redacted": True,
        }

    async def get_readiness(self, user: User, org_context: OrgContext) -> dict:
        """Consolidated readiness — reuses launch evaluator; read-only."""
        from app.pilot.launch_readiness import evaluate_customer_launch_readiness, integration_freshness_ok
        from app.models.delivery import DeliveryEnvironment
        from app.services.integration_readiness import IntegrationReadinessService

        organization_id = self._ensure_read(user, org_context)
        sessions = await self.repo.list_for_org(organization_id)

        readiness_svc = IntegrationReadinessService(self.session)
        conns = await readiness_svc.list_connections(user, org_context)
        enrollment_row = (
            await self.session.execute(
                select(PilotEnrollment).where(PilotEnrollment.organization_id == organization_id),
            )
        ).scalar_one_or_none()

        org_allowed = (
            getattr(settings, "PILOT_MODE_ALL_ORGS", False)
            or organization_id in getattr(settings, "PILOT_ORGANIZATION_IDS", [])
        )
        enrollment = {
            "id": enrollment_row.id if enrollment_row else None,
            "kill_switch": enrollment_row.kill_switch if enrollment_row else False,
            "operation_limit": enrollment_row.operation_limit if enrollment_row else None,
            "contacts": enrollment_row.contacts if enrollment_row else {},
        } if enrollment_row else {}

        integrations = []
        for c in conns:
            meta = c.validation_metadata or {}
            integrations.append({
                "id": c.id,
                "provider_type": c.provider_type,
                "lifecycle_state": c.lifecycle_state,
                "provider_mode": c.provider_mode,
                "capabilities": c.capabilities or {},
                "freshness_ok": integration_freshness_ok(c.last_validated_at),
                "rbac_evidence": meta.get("rbac_evidence"),
            })

        envs = list((await self.session.execute(
            select(DeliveryEnvironment).where(DeliveryEnvironment.organization_id == organization_id),
        )).scalars().all())

        payload = {
            "pilot_mode_enabled": getattr(settings, "PILOT_MODE_ENABLED", False),
            "org_allowlisted": org_allowed,
            "enrollment": enrollment,
            "integrations": integrations,
            "environments": [{"tier": e.tier, "name": e.name} for e in envs],
            "contacts": enrollment.get("contacts") or {},
            "backup_restore_documented": bool(
                any(s.status == "READY_FOR_PILOT" for s in sessions)
                or (enrollment.get("contacts") or {}).get("backup_restore_acknowledged"),
            ),
        }
        verdict = evaluate_customer_launch_readiness(payload)

        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_READINESS_EVALUATED,
            organization_id=organization_id,
            payload={"verdict": verdict["verdict"], "onboarding": True},
        )
        self._record_readiness_metric(verdict["verdict"])

        return {
            **verdict,
            "sessions": sessions,
            "evaluated_at": datetime.now(UTC).isoformat(),
            "read_only": True,
        }

    def get_customer_pilot_prerequisites(self) -> dict:
        return {
            "items": [
                {"key": "namespace", "label": "Non-production Kubernetes namespace", "required": True},
                {"key": "repository", "label": "Single source repository (read-only)", "required": True},
                {"key": "prometheus", "label": "Prometheus-compatible metrics endpoint", "required": True},
                {"key": "rbac", "label": "Namespace-scoped RBAC (no secrets/exec/delete)", "required": True},
                {"key": "approver", "label": "Named pilot approver", "required": True},
            ],
            "documentation_links": [
                {"title": "Integration Onboarding Guide", "path": "/docs/customer-pilot/INTEGRATION_ONBOARDING_GUIDE.md"},
                {"title": "Kubernetes RBAC Templates", "path": "/docs/customer-pilot/KUBERNETES_RBAC_TEMPLATES.md"},
                {"title": "Source Control Permissions", "path": "/docs/customer-pilot/SOURCE_CONTROL_PERMISSIONS.md"},
                {"title": "Prometheus Requirements", "path": "/docs/customer-pilot/PROMETHEUS_REQUIREMENTS.md"},
                {"title": "Customer Prerequisites", "path": "/docs/customer-pilot/CUSTOMER_PREREQUISITES.md"},
            ],
        }

    async def assert_no_pilot_side_effects(self, organization_id: str) -> dict:
        """Diagnostic helper for tests — counts pilot artifacts."""
        enrollments = (await self.session.execute(
            select(func.count()).select_from(PilotEnrollment).where(
                PilotEnrollment.organization_id == organization_id,
            ),
        )).scalar_one()
        ops = (await self.session.execute(
            select(func.count()).select_from(PilotLiveOperation).where(
                PilotLiveOperation.organization_id == organization_id,
            ),
        )).scalar_one()
        stages = (await self.session.execute(
            select(func.count()).select_from(PilotStage).where(
                PilotStage.organization_id == organization_id,
            ),
        )).scalar_one()
        return {"enrollments": enrollments, "operations": ops, "stages": stages}

    def _record_session_metric(self, outcome: str, provider: str) -> None:
        try:
            from app.observability import metrics
            metrics.record_onboarding_session(provider, outcome)
        except Exception:
            pass

    def _record_validation_metric(self, provider: str, status: str) -> None:
        try:
            from app.observability import metrics
            metrics.record_onboarding_validation(provider, status)
        except Exception:
            pass

    def _record_validation_duration(self, provider: str, duration: float) -> None:
        try:
            from app.observability import metrics
            metrics.record_onboarding_validation_duration(provider, duration)
        except Exception:
            pass

    def _record_rbac_gap(self, provider: str, gap_type: str) -> None:
        try:
            from app.observability import metrics
            metrics.record_onboarding_rbac_gap(provider, gap_type)
        except Exception:
            pass

    def _record_readiness_metric(self, verdict: str) -> None:
        try:
            from app.observability import metrics
            metrics.record_onboarding_readiness(verdict)
        except Exception:
            pass
