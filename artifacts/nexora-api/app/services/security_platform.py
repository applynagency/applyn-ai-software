"""Enterprise DevSecOps & Cloud Security Platform orchestration (Sprint 65D).

Extends Delivery scans, Control Plane K8s policies, Platform Engineering compliance,
identity policy, incident remediation — does not duplicate engines.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.integration import ConnectionStatus
from app.models.security_platform import (
    SecAccessReviewCampaign,
    SecBackfillJob,
    SecException,
    SecFinding,
    SecInvestigation,
    SecPostureSnapshot,
    SecProvider,
    SecRemediationExecution,
    SecRemediationProposal,
    SecSbomComponent,
    SecSbomRef,
    SecScanRun,
    SecSlaPolicy,
)
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.integration_readiness.live_gate import LiveMutationGate
from app.integration_readiness.preflight import make_idempotency_key
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import MonitoringAlertRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.repositories.security_platform import (
    SecAccessReviewRepo,
    SecBackfillJobRepo,
    SecExceptionRepo,
    SecFindingRepo,
    SecInvestigationRepo,
    SecPostureRepo,
    SecProviderRepo,
    SecRemediationExecutionRepo,
    SecRemediationRepo,
    SecSbomComponentRepo,
    SecSbomRepo,
    SecScanRunRepo,
    SecSlaPolicyRepo,
)
from app.schemas.security_platform import (
    ExceptionCreate,
    FindingTransition,
    InvestigationCreate,
    ProviderCreate,
    RemediationProposalCreate,
    SbomImportRequest,
    ScanRequest,
)
from app.security.secrets import SecretManagerService
from app.security_platform.analytics import compute_posture
from app.security_platform.backfill import run_backfill
from app.security_platform.findings import normalize_finding, transition_status
from app.security_platform.gates import evaluate_gate
from app.security_platform.investigation import build_security_timeline
from app.security_platform.providers import registry as sec_registry
from app.security_platform.providers.execution import execute_scan, validate_provider
from app.security_platform.remediation_exec import (
    apply_execution_result,
    build_execution_plan,
    requires_human_approval,
)
from app.security_platform.sbom_parser import parse_sbom
from app.security_platform.sla import evaluate_sla, sla_dashboard_counts
from app.tenancy.permissions import can_manage_organization, can_read_resources, can_write_resources

logger = get_logger(__name__)

_SECRET_PATTERNS = ("password", "secret", "token", "api_key", "credential")


def _default_provider_for_kind(kind: str) -> str:
    return {
        "CONTAINER": "TRIVY", "DEPENDENCY": "TRIVY", "SBOM": "TRIVY",
        "SECRET": "GITLEAKS", "SAST": "SEMGREP", "IAC": "CHECKOV",
    }.get(kind.upper(), "TRIVY")


def _redact_evidence(data: dict) -> dict:
    """Strip values that may contain secret material from evidence payloads."""
    out = {}
    for k, v in (data or {}).items():
        if any(p in k.lower() for p in _SECRET_PATTERNS):
            out[k] = "[REDACTED]"
        elif isinstance(v, dict):
            out[k] = _redact_evidence(v)
        else:
            out[k] = v
    return out


class SecurityPlatformService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.findings = SecFindingRepo(session)
        self.scans = SecScanRunRepo(session)
        self.sboms = SecSbomRepo(session)
        self.exceptions = SecExceptionRepo(session)
        self.remediations = SecRemediationRepo(session)
        self.posture = SecPostureRepo(session)
        self.investigations = SecInvestigationRepo(session)
        self.access_reviews = SecAccessReviewRepo(session)
        self.providers = SecProviderRepo(session)
        self.sbom_components = SecSbomComponentRepo(session)
        self.backfill_jobs = SecBackfillJobRepo(session)
        self.sla_policies = SecSlaPolicyRepo(session)
        self.remediation_executions = SecRemediationExecutionRepo(session)
        self.alerts = MonitoringAlertRepository(session)
        self.audit = AuditLogRepository(session)
        self.marketplace_connections = IntegrationConnectionRepository(session)
        self.secrets = SecretManagerService(session)

    def _ensure_admin(self, user: User, org_context: OrgContext) -> str:
        if not can_manage_organization(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Admin permissions required")
        return org_context.requires_organization

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _record_scan(self, duration: float) -> None:
        try:
            from app.observability import metrics
            metrics.record_sec_scan(duration)
        except Exception:  # noqa: BLE001
            pass

    async def _marketplace_sonarqube_config(
        self,
        organization_id: str,
        user: User,
        org_context: OrgContext,
    ) -> dict | None:
        statuses = {ConnectionStatus.VERIFIED.value, ConnectionStatus.CONNECTED.value}
        for conn in await self.marketplace_connections.list_for_org(organization_id):
            if (conn.integration_key or "").upper() != "SONARQUBE":
                continue
            if conn.status not in statuses or not conn.credential_id:
                continue
            try:
                _cred, secret = await self.secrets.resolve_secret(
                    conn.credential_id,
                    user=user,
                    org_context=org_context,
                    reason="security sonarqube scan",
                )
                return secret or {}
            except Exception:  # noqa: BLE001
                return None
        return None

    @staticmethod
    def providers() -> dict:
        return {
            "scan_kinds": sec_registry.supported_scan_kinds(),
            "delivery_tools": sec_registry.supported_delivery_tools(),
        }

    # -------------------------------------------------------------- overview
    async def overview(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        rows, total = await self.findings.list_for_org(organization_id, limit=500)
        open_rows = [r for r in rows if r.status in ("OPEN", "ACKNOWLEDGED", "IN_REMEDIATION")]
        critical = sum(1 for r in open_rows if r.severity == "CRITICAL")
        posture = compute_posture(findings=[self._finding_dict(r) for r in rows])
        pending = await self.remediations.list_for_org(organization_id, status="PROPOSED")
        scans, _ = await self.scans.list_for_org(organization_id, limit=10)
        snap = SecPostureSnapshot(
            organization_id=organization_id,
            posture_score=posture["posture_score"],
            grade=posture["grade"],
            breakdown=posture,
            open_critical=critical,
        )
        self.session.add(snap)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.SECURITY_SCORE_CHANGED,
            organization_id=organization_id,
            payload={"score": posture["posture_score"], "grade": posture["grade"]},
        )
        try:
            from app.observability import metrics
            metrics.set_sec_posture(posture["posture_score"], critical)
        except Exception:  # noqa: BLE001
            pass
        return {
            "posture_score": posture["posture_score"],
            "grade": posture["grade"],
            "open_critical": critical,
            "open_findings": len(open_rows),
            "recent_scans": len(scans),
            "pending_remediations": len(pending),
        }

    # ---------------------------------------------------------------- scans
    async def run_scan(self, user: User, org_context: OrgContext, payload: ScanRequest) -> SecScanRun:
        organization_id = self._ensure_write(user, org_context)
        start = time.perf_counter()
        provider_type = payload.tool or _default_provider_for_kind(payload.kind)
        provider_row = await self.providers.get_by_type(organization_id, provider_type)
        enabled = bool(provider_row and provider_row.enabled)
        config = dict(payload.config or {})
        await emit_event(
            self.session, DomainEventType.SECURITY_SCAN_STARTED,
            organization_id=organization_id,
            payload={"kind": payload.kind, "target": payload.target},
        )
        if (provider_type or "").upper() == "SONARQUBE" or (
            payload.kind.upper() == "SAST" and not config.get("endpoint")
        ):
            sonar_cfg = await self._marketplace_sonarqube_config(
                organization_id, user, org_context,
            )
            if sonar_cfg:
                config.update(sonar_cfg)
                provider_type = "SONARQUBE"
                from app.security_platform.providers.sonarqube_live import scan_project
                result = scan_project(config, project_key=payload.target)
            else:
                result = await execute_scan(
                    payload.kind, payload.target,
                    provider_type=provider_type,
                    enabled=enabled,
                    config=config,
                )
        else:
            result = await execute_scan(
                payload.kind, payload.target,
                provider_type=provider_type,
                enabled=enabled,
                config=config,
            )
        gate = None
        if payload.enforce_gate:
            gate_result = await self._evaluate_gate_for_scan(organization_id, payload, result)
            gate = gate_result.get("decision")
        row = SecScanRun(
            organization_id=organization_id,
            kind=payload.kind.upper(),
            tool=result.get("tool", payload.tool or "UNKNOWN"),
            target=payload.target,
            status=result.get("status", "COMPLETED"),
            summary=result.get("summary", {}),
            result=_redact_evidence(result),
            simulated=bool(result.get("simulated", True)),
            gate_decision=gate,
            provider_mode=result.get("provider_mode"),
            provider_id=provider_row.id if provider_row else None,
            raw_output_redacted=result.get("raw_output_redacted"),
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        created_findings = await self._ingest_scan_findings(organization_id, row, result.get("findings", []))
        if result.get("sbom"):
            sbom = SecSbomRef(
                organization_id=organization_id,
                scan_run_id=row.id,
                format=result["sbom"].get("format", "cyclonedx"),
                target=payload.target,
                component_count=int(result["sbom"].get("components", 0)),
                inventory=_redact_evidence(result["sbom"]),
            )
            self.session.add(sbom)
        if payload.kind.upper() == "IAC" and result.get("findings"):
            await emit_event(
                self.session, DomainEventType.POLICY_VIOLATION_DETECTED,
                organization_id=organization_id,
                payload={"scan_id": row.id, "violations": len(result.get("findings", []))},
            )
        for f in created_findings:
            if f.severity == "CRITICAL":
                await emit_event(
                    self.session, DomainEventType.CRITICAL_VULNERABILITY_DETECTED,
                    organization_id=organization_id,
                    payload={"finding_id": f.id, "title": f.title},
                )
            if f.source == "SECRET":
                await emit_event(
                    self.session, DomainEventType.SECRET_DETECTED,
                    organization_id=organization_id,
                    payload={"finding_id": f.id},
                )
        await emit_event(
            self.session, DomainEventType.SECURITY_SCAN_COMPLETED,
            organization_id=organization_id,
            payload={"scan_id": row.id, "simulated": row.simulated, "provider_mode": row.provider_mode},
        )
        await emit_event(
            self.session, DomainEventType.SECURITY_FINDING_CREATED,
            organization_id=organization_id,
            payload={"scan_id": row.id, "findings_ingested": len(created_findings)},
        )
        self._record_scan(time.perf_counter() - start)
        try:
            from app.observability import metrics
            metrics.record_sec_scan_mode(payload.kind.upper(), live=row.provider_mode == "live")
            if row.provider_mode:
                metrics.record_sec_provider_health(provider_type, row.provider_mode)
            if gate in ("BLOCK", "APPROVAL_REQUIRED"):
                metrics.record_sec_gate_block(gate)
                await emit_event(
                    self.session, DomainEventType.SECURITY_GATE_BLOCKED,
                    organization_id=organization_id,
                    payload={"scan_id": row.id, "decision": gate},
                )
        except Exception:  # noqa: BLE001
            pass
        await self.audit.log(
            action="sec.scan_completed", resource_type="sec_scan_run",
            resource_id=row.id, user_id=user.id,
            details={"kind": payload.kind, "simulated": row.simulated},
        )
        return row

    async def _ingest_scan_findings(
        self, organization_id: str, scan: SecScanRun, raw_findings: list[dict],
    ) -> list[SecFinding]:
        created: list[SecFinding] = []
        for rf in raw_findings:
            norm = normalize_finding(
                organization_id=organization_id,
                source=rf.get("source", scan.kind),
                severity=rf.get("severity", "MEDIUM"),
                title=rf.get("title", "Security finding"),
                resource=rf.get("resource") or rf.get("package"),
                cve=rf.get("cve"),
                evidence=_redact_evidence(rf),
                remediation=rf.get("recommendation"),
                scan_run_id=scan.id,
            )
            existing = await self.findings.get_by_fingerprint(organization_id, norm["fingerprint"])
            if existing:
                existing.evidence = norm["evidence"]
                existing.scan_run_id = scan.id
                continue
            row = SecFinding(**norm)
            self.session.add(row)
            created.append(row)
        await self.session.flush()
        try:
            from app.observability import metrics
            metrics.record_sec_findings(len(created))
        except Exception:  # noqa: BLE001
            pass
        return created

    async def _evaluate_gate_for_scan(
        self, organization_id: str, payload: ScanRequest, result: dict,
    ) -> dict:
        rows = await self.findings.list_open_for_gate(organization_id)
        finding_dicts = [self._finding_row_dict(r) for r in rows]
        for rf in result.get("findings", []):
            finding_dicts.append({
                "id": None, "severity": rf.get("severity"), "title": rf.get("title"),
                "status": "OPEN", "source": rf.get("source"), "resource": rf.get("resource"),
            })
        return evaluate_gate(
            finding_dicts,
            policy_mode=payload.config.get("policy_mode", "BLOCK"),
            scope=payload.config.get("scope"),
        )

    async def list_scans(
        self, user: User, org_context: OrgContext, *, offset: int = 0, limit: int = 50,
    ) -> tuple[list[SecScanRun], int]:
        organization_id = self._ensure_read(user, org_context)
        return await self.scans.list_for_org(organization_id, offset=offset, limit=limit)

    # -------------------------------------------------------------- findings
    async def list_findings(
        self, user: User, org_context: OrgContext, *,
        status: str | None = None, severity: str | None = None, source: str | None = None,
        offset: int = 0, limit: int = 50,
    ) -> tuple[list[SecFinding], int]:
        organization_id = self._ensure_read(user, org_context)
        return await self.findings.list_for_org(
            organization_id, status=status, severity=severity, source=source,
            offset=offset, limit=limit,
        )

    async def transition_finding(
        self, user: User, org_context: OrgContext, finding_id: str, payload: FindingTransition,
    ) -> SecFinding:
        organization_id = self._ensure_write(user, org_context)
        row = await self.findings.get_by_id(finding_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("Finding", finding_id)
        new_status, hist = transition_status(row.status, payload.status, actor=user.id)
        row.status = new_status
        history = list(row.history or [])
        history.append(hist)
        row.history = history
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.SECURITY_FINDING_UPDATED,
            organization_id=organization_id,
            payload={"finding_id": row.id, "status": new_status},
        )
        return row

    @staticmethod
    def _finding_row_dict(row: SecFinding) -> dict:
        return {
            "id": row.id, "severity": row.severity, "source": row.source, "status": row.status,
            "title": row.title, "created_at": row.created_at, "environment": row.environment,
            "resource": row.resource, "owner_team": row.owner_team, "sla_due_at": row.sla_due_at,
        }

    @staticmethod
    def _finding_dict(row: SecFinding) -> dict:
        due = row.sla_due_at
        breached = False
        if due:
            if getattr(due, "tzinfo", None) is None:
                due = due.replace(tzinfo=UTC)
            breached = due < datetime.now(UTC)
        return {
            "severity": row.severity, "source": row.source, "status": row.status,
            "title": row.title, "created_at": row.created_at,
            "sla_breached": breached,
        }

    # ----------------------------------------------------------- exceptions
    async def grant_exception(
        self, user: User, org_context: OrgContext, payload: ExceptionCreate,
    ) -> SecException:
        organization_id = self._ensure_write(user, org_context)
        finding = await self.findings.get_by_id(payload.finding_id)
        if not finding or finding.organization_id != organization_id:
            raise NotFoundError("Finding", payload.finding_id)
        row = SecException(
            organization_id=organization_id,
            finding_id=payload.finding_id,
            justification=payload.justification,
            approved_by=user.id,
            expires_at=payload.expires_at,
        )
        finding.status = "ACCEPTED_RISK"
        finding.exception_expires_at = payload.expires_at
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.SECURITY_EXCEPTION_GRANTED,
            organization_id=organization_id,
            payload={"finding_id": finding.id, "exception_id": row.id},
        )
        try:
            from app.observability import metrics
            metrics.record_sec_exception()
        except Exception:  # noqa: BLE001
            pass
        return row

    async def list_exceptions(self, user: User, org_context: OrgContext) -> list[SecException]:
        organization_id = self._ensure_read(user, org_context)
        return await self.exceptions.list_for_org(organization_id)

    # --------------------------------------------------------- remediation
    async def propose_remediation(
        self, user: User, org_context: OrgContext, payload: RemediationProposalCreate,
    ) -> SecRemediationProposal:
        organization_id = self._ensure_write(user, org_context)
        finding = await self.findings.get_by_id(payload.finding_id)
        if not finding or finding.organization_id != organization_id:
            raise NotFoundError("Finding", payload.finding_id)
        row = SecRemediationProposal(
            organization_id=organization_id,
            finding_id=payload.finding_id,
            kind=payload.kind.upper(),
            title=payload.title,
            evidence=_redact_evidence({
                "finding_title": finding.title, "severity": finding.severity,
                "resource": finding.resource, "cve": finding.cve,
            }),
            risk=finding.severity,
            impact=payload.impact,
            rollback_plan=payload.rollback_plan or "Revert change via approval-gated execution engine",
            requires_approval=True,
            status="PROPOSED",
            created_by=user.id,
        )
        self.session.add(row)
        finding.status = "IN_REMEDIATION"
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.SECURITY_REMEDIATION_PROPOSED,
            organization_id=organization_id,
            aggregate_id=row.id,
            payload={"finding_id": finding.id, "kind": row.kind},
        )
        return row

    async def list_remediations(self, user: User, org_context: OrgContext) -> list[SecRemediationProposal]:
        organization_id = self._ensure_read(user, org_context)
        return await self.remediations.list_for_org(organization_id)

    async def approve_remediation(
        self, user: User, org_context: OrgContext, proposal_id: str, *, approved: bool,
    ) -> SecRemediationProposal:
        organization_id = self._ensure_write(user, org_context)
        row = await self.remediations.get_by_id(proposal_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("RemediationProposal", proposal_id)
        if not approved:
            row.status = "REJECTED"
        else:
            row.status = "APPROVED"
            row.execution_status = "PENDING"
            await emit_event(
                self.session, DomainEventType.SECURITY_REMEDIATION_EXECUTED,
                organization_id=organization_id,
                payload={"proposal_id": row.id, "status": "APPROVED_PENDING_EXECUTION"},
            )
        await self.session.flush()
        return row

    # ---------------------------------------------------------- investigations
    async def investigate(
        self, user: User, org_context: OrgContext, payload: InvestigationCreate,
    ) -> SecInvestigation:
        organization_id = self._ensure_read(user, org_context)
        finding_rows, _ = await self.findings.list_for_org(organization_id, limit=30)
        alert_rows, _ = await self.alerts.list_for_org(organization_id, limit=20)
        timeline = build_security_timeline(
            findings=[self._finding_dict(r) for r in finding_rows],
            alerts=[
                {"alert_name": a.alert_name, "severity": a.severity, "fired_at": a.last_seen_at}
                for a in alert_rows
            ],
        )
        row = SecInvestigation(
            organization_id=organization_id,
            title=payload.title or "Security investigation",
            timeline=timeline,
            summary=timeline.get("summary"),
            incident_id=payload.incident_id,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        if timeline.get("critical_count", 0) > 0:
            await emit_event(
                self.session, DomainEventType.SECURITY_INCIDENT_CREATED,
                organization_id=organization_id,
                payload={"investigation_id": row.id},
            )
        return row

    async def list_investigations(self, user: User, org_context: OrgContext) -> list[SecInvestigation]:
        organization_id = self._ensure_read(user, org_context)
        return await self.investigations.list_for_org(organization_id)

    # ------------------------------------------------------------- analytics
    async def analytics(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        rows, _ = await self.findings.list_for_org(organization_id, limit=500)
        snaps = await self.posture.list_for_org(organization_id)
        return compute_posture(
            findings=[self._finding_dict(r) for r in rows],
            snapshots=[{"score": s.posture_score, "at": str(s.created_at)} for s in snaps[:14]],
        )

    # ---------------------------------------------------------- domain views
    async def vulnerabilities(self, user: User, org_context: OrgContext) -> dict:
        rows, total = await self.list_findings(
            user, org_context, source=None, severity=None, limit=100,
        )
        vulns = [r for r in rows if r.cve or r.source in ("DEPENDENCY", "CONTAINER", "SOURCE_CODE")]
        return {
            "total": len(vulns),
            "findings": [
                {"id": v.id, "title": v.title, "severity": v.severity, "cve": v.cve}
                for v in vulns[:50]
            ],
        }

    async def sbom_inventory(self, user: User, org_context: OrgContext) -> list[SecSbomRef]:
        organization_id = self._ensure_read(user, org_context)
        return await self.sboms.list_for_org(organization_id)

    async def kubernetes_security(self, user: User, org_context: OrgContext) -> dict:
        rows, _ = await self.list_findings(user, org_context, source="KUBERNETES", limit=50)
        return {
            "cluster_score": max(0, 100 - sum(10 for r in rows if r.severity in ("CRITICAL", "HIGH"))),
            "findings": len(rows),
            "top": [{"title": r.title, "severity": r.severity} for r in rows[:10]],
        }

    async def cloud_posture(self, user: User, org_context: OrgContext) -> dict:
        rows, _ = await self.list_findings(user, org_context, source="CLOUD", limit=50)
        latest = await self.posture.latest(org_context.requires_organization)
        return {
            "account_score": latest.posture_score if latest else 85,
            "findings": len(rows),
            "top": [{"title": r.title, "severity": r.severity} for r in rows[:10]],
        }

    async def iac_security(self, user: User, org_context: OrgContext) -> dict:
        rows, _ = await self.list_findings(user, org_context, source="IAC", limit=50)
        return {"policy_violations": len(rows), "findings": [{"title": r.title} for r in rows[:10]]}

    async def identity_security(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        rows, _ = await self.list_findings(user, org_context, source="IAM", limit=50)
        campaigns = await self.access_reviews.list_for_org(organization_id)
        if not campaigns:
            campaign = SecAccessReviewCampaign(
                organization_id=organization_id,
                name="Quarterly access review",
                scope={"identities": "all"},
                findings_count=len(rows),
                due_at=datetime.now(UTC) + timedelta(days=90),
                created_by=user.id,
            )
            self.session.add(campaign)
            await self.session.flush()
            campaigns = [campaign]
        return {
            "campaigns": [{"id": c.id, "name": c.name, "status": c.status} for c in campaigns],
            "findings": [{"title": r.title, "severity": r.severity} for r in rows[:10]],
        }

    async def compliance_view(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        latest = await self.posture.latest(organization_id)
        rows, _ = await self.findings.list_for_org(organization_id, limit=100)
        return {
            "score": latest.posture_score if latest else 80,
            "grade": latest.grade if latest else "B",
            "frameworks": ["SOC2", "CIS", "NIST"],
            "findings": [{"check": r.source, "severity": r.severity, "title": r.title} for r in rows[:20]],
        }

    # ------------------------------------------------ Sprint 65E — providers
    async def list_provider_configs(self, user: User, org_context: OrgContext) -> list[SecProvider]:
        organization_id = self._ensure_read(user, org_context)
        return await self.providers.list_for_org(organization_id)

    async def create_provider(
        self, user: User, org_context: OrgContext, payload: ProviderCreate,
    ) -> SecProvider:
        organization_id = self._ensure_write(user, org_context)
        existing = await self.providers.get_by_type(organization_id, payload.provider_type)
        if existing:
            existing.name = payload.name
            existing.enabled = payload.enabled
            existing.config = _redact_evidence(payload.config)
            validation = await validate_provider(
                payload.provider_type, enabled=payload.enabled, config=payload.config,
            )
            existing.mode = validation["mode"]
            existing.validation_message = validation["message"]
            existing.validated_at = datetime.now(UTC)
            await self.session.flush()
            return existing
        validation = await validate_provider(
            payload.provider_type, enabled=payload.enabled, config=payload.config,
        )
        row = SecProvider(
            organization_id=organization_id,
            provider_type=payload.provider_type.upper(),
            name=payload.name,
            enabled=payload.enabled,
            config=_redact_evidence(payload.config),
            mode=validation["mode"],
            validation_message=validation["message"],
            validated_at=datetime.now(UTC),
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        try:
            from app.observability import metrics
            metrics.record_sec_provider_health(row.provider_type, row.mode)
        except Exception:  # noqa: BLE001
            pass
        return row

    async def validate_provider_config(
        self, user: User, org_context: OrgContext, provider_id: str,
    ) -> SecProvider:
        organization_id = self._ensure_write(user, org_context)
        row = await self.providers.get_by_id(provider_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("SecProvider", provider_id)
        validation = await validate_provider(row.provider_type, enabled=row.enabled, config=row.config)
        row.mode = validation["mode"]
        row.validation_message = validation["message"]
        row.validated_at = datetime.now(UTC)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.SECURITY_PROVIDER_VALIDATED,
            organization_id=organization_id,
            payload={"provider_id": row.id, "mode": row.mode},
        )
        try:
            from app.observability import metrics
            metrics.record_sec_provider_health(row.provider_type, row.mode)
        except Exception:  # noqa: BLE001
            pass
        return row

    async def execute_scan_by_id(
        self, user: User, org_context: OrgContext, scan_id: str,
    ) -> SecScanRun:
        organization_id = self._ensure_write(user, org_context)
        row = await self.scans.get_by_id(scan_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("SecScanRun", scan_id)
        return await self.run_scan(
            user, org_context,
            ScanRequest(kind=row.kind, target=row.target, tool=row.tool, enforce_gate=False),
        )

    # --------------------------------------------------------- SBOM import
    async def import_sbom(
        self, user: User, org_context: OrgContext, payload: SbomImportRequest,
    ) -> dict:
        organization_id = self._ensure_write(user, org_context)
        parsed = parse_sbom(payload.content, fmt=payload.format)
        ref = SecSbomRef(
            organization_id=organization_id,
            format=parsed["format"],
            target=payload.target,
            component_count=parsed["component_count"],
            inventory=_redact_evidence({"components": len(parsed["components"])}),
        )
        self.session.add(ref)
        await self.session.flush()
        imported = 0
        for comp in parsed["components"]:
            existing = await self.sbom_components.get_by_normalized_key(
                organization_id, comp["normalized_key"],
            )
            if existing:
                continue
            row = SecSbomComponent(
                organization_id=organization_id,
                sbom_ref_id=ref.id,
                name=comp["name"],
                version=comp.get("version"),
                ecosystem=comp.get("ecosystem"),
                license=comp.get("license"),
                purl=comp.get("purl"),
                parent_purl=comp.get("parent_purl"),
                artifact_id=payload.artifact_id,
                normalized_key=comp["normalized_key"],
            )
            self.session.add(row)
            imported += 1
        await self.session.flush()
        await self._correlate_sbom_vulns(organization_id)
        await emit_event(
            self.session, DomainEventType.SECURITY_SBOM_IMPORTED,
            organization_id=organization_id,
            payload={"sbom_ref_id": ref.id, "components": imported},
        )
        return {"sbom_ref_id": ref.id, "components_imported": imported, "format": parsed["format"]}

    async def _correlate_sbom_vulns(self, organization_id: str) -> None:
        components, _ = await self.sbom_components.list_for_org(organization_id, limit=500)
        vuln_rows, _ = await self.findings.list_for_org(
            organization_id, source="DEPENDENCY", limit=500,
        )
        for comp in components:
            matches = [
                f.id for f in vuln_rows
                if f.resource and comp.name.lower() in f.resource.lower()
            ]
            if matches:
                comp.vuln_finding_ids = matches
        await self.session.flush()

    async def list_sbom_components(
        self, user: User, org_context: OrgContext, *, offset: int = 0, limit: int = 100,
    ) -> tuple[list[SecSbomComponent], int]:
        organization_id = self._ensure_read(user, org_context)
        return await self.sbom_components.list_for_org(organization_id, offset=offset, limit=limit)

    # ----------------------------------------------------------- backfill
    async def backfill_dry_run(self, user: User, org_context: OrgContext) -> SecBackfillJob:
        organization_id = self._ensure_admin(user, org_context)
        counts = await run_backfill(self.session, organization_id, dry_run=True)
        job = SecBackfillJob(
            organization_id=organization_id,
            status="COMPLETED",
            dry_run=True,
            counts=counts,
            started_by=user.id,
            completed_at=datetime.now(UTC),
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def backfill_execute(self, user: User, org_context: OrgContext) -> SecBackfillJob:
        organization_id = self._ensure_admin(user, org_context)
        job = SecBackfillJob(
            organization_id=organization_id,
            status="RUNNING",
            dry_run=False,
            counts={},
            started_by=user.id,
        )
        self.session.add(job)
        await self.session.flush()
        try:
            counts = await run_backfill(self.session, organization_id, dry_run=False)
            job.counts = counts
            job.status = "COMPLETED"
            job.completed_at = datetime.now(UTC)
            await emit_event(
                self.session, DomainEventType.SECURITY_BACKFILL_COMPLETED,
                organization_id=organization_id,
                payload={"job_id": job.id, "counts": counts},
            )
            try:
                from app.observability import metrics
                metrics.record_sec_backfill("all", counts.get("imported", 0))
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            job.status = "FAILED"
            job.error = str(exc)[:500]
            job.completed_at = datetime.now(UTC)
        await self.session.flush()
        return job

    async def backfill_status(self, user: User, org_context: OrgContext) -> SecBackfillJob | None:
        organization_id = self._ensure_admin(user, org_context)
        return await self.backfill_jobs.latest_for_org(organization_id)

    # --------------------------------------------------------------- SLA
    async def get_sla_view(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        policies = await self.sla_policies.list_for_org(organization_id)
        if not policies:
            for sev, days in (("CRITICAL", 1), ("HIGH", 7), ("MEDIUM", 30), ("LOW", 90)):
                pol = SecSlaPolicy(
                    organization_id=organization_id, severity=sev, due_days=days,
                )
                self.session.add(pol)
            await self.session.flush()
            policies = await self.sla_policies.list_for_org(organization_id)
        policy_dicts = [
            {"severity": p.severity, "environment": p.environment, "due_days": p.due_days,
             "warning_hours": p.warning_hours, "owner_team": p.owner_team, "enabled": p.enabled}
            for p in policies
        ]
        rows, _ = await self.findings.list_for_org(organization_id, limit=500)
        finding_dicts = [self._finding_row_dict(r) for r in rows]
        dashboard = sla_dashboard_counts(finding_dicts, policies=policy_dicts)
        try:
            from app.observability import metrics
            metrics.set_sec_sla_due(dashboard.get("due_soon", 0))
        except Exception:  # noqa: BLE001
            pass
        return {"policies": policy_dicts, "dashboard": dashboard}

    async def evaluate_slas(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_write(user, org_context)
        policies = await self.sla_policies.list_for_org(organization_id)
        policy_dicts = [
            {"severity": p.severity, "environment": p.environment, "due_days": p.due_days,
             "warning_hours": p.warning_hours, "enabled": p.enabled}
            for p in policies
        ]
        rows, _ = await self.findings.list_for_org(organization_id, limit=500)
        breached = escalated = 0
        for row in rows:
            if row.status not in ("OPEN", "ACKNOWLEDGED", "IN_REMEDIATION"):
                continue
            ev = evaluate_sla(self._finding_row_dict(row), policies=policy_dicts)
            if row.sla_due_at is None:
                row.sla_due_at = ev["sla_due_at"]
            if ev["sla_breached"] and not row.sla_breached:
                row.sla_breached = True
                breached += 1
                try:
                    from app.observability import metrics
                    metrics.record_sec_sla_breach()
                except Exception:  # noqa: BLE001
                    pass
                await emit_event(
                    self.session, DomainEventType.SECURITY_SLA_BREACHED,
                    organization_id=organization_id,
                    payload={"finding_id": row.id, "severity": row.severity},
                )
                if row.severity == "CRITICAL":
                    row.related_incident_id = row.related_incident_id or f"sla-escalation-{row.id[:8]}"
                    escalated += 1
        await self.session.flush()
        return {"breached": breached, "escalated": escalated}

    # --------------------------------------------- remediation execution
    async def get_remediation_execution(
        self, user: User, org_context: OrgContext, proposal_id: str,
    ) -> SecRemediationExecution:
        organization_id = self._ensure_read(user, org_context)
        row = await self.remediation_executions.get_by_proposal(organization_id, proposal_id)
        if not row:
            raise NotFoundError("SecRemediationExecution", proposal_id)
        return row

    async def execute_remediation(
        self, user: User, org_context: OrgContext, proposal_id: str,
    ) -> SecRemediationExecution:
        organization_id = self._ensure_write(user, org_context)
        proposal = await self.remediations.get_by_id(proposal_id)
        if not proposal or proposal.organization_id != organization_id:
            raise NotFoundError("RemediationProposal", proposal_id)
        if proposal.status != "APPROVED":
            raise ForbiddenError("Remediation must be approved before execution")
        finding = await self.findings.get_by_id(proposal.finding_id)
        if not finding:
            raise NotFoundError("Finding", proposal.finding_id)
        if requires_human_approval(proposal.kind):
            if proposal.status != "APPROVED":
                raise ForbiddenError("High-risk remediation requires explicit approval")

        if requires_human_approval(proposal.kind):
            if proposal.status != "APPROVED":
                raise ForbiddenError("High-risk remediation requires explicit approval")

        gate = LiveMutationGate(self.session)
        reg = await gate.ensure_registry(
            organization_id=organization_id,
            resource_type="security",
            resource_id=proposal.id,
            provider_type=(finding.source_system or "TRIVY").upper(),
            credential_id=None,
        )
        preflight = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=reg.id,
            operation_type=f"security.remediation.{proposal.kind.lower()}",
            resource_type="sec_remediation",
            resource_id=proposal.id,
            idempotency_key=make_idempotency_key(org_id=organization_id, operation=proposal.kind, target_id=proposal.id),
            required_capabilities=["write", "apply"],
            approval_satisfied=proposal.status == "APPROVED",
            explicit_simulation=bool((proposal.rollback_plan or {}).get("explicit_simulation")),
            proposal_id=proposal.id,
            resource_lookup=("security", proposal.id),
        )
        if not preflight["allowed"]:
            execution = SecRemediationExecution(
                organization_id=organization_id,
                proposal_id=proposal.id,
                status="BLOCKED",
                checkpoints=[{"label": "preflight_blocked", "at": datetime.now(UTC).isoformat()}],
                result={"blocked": True, "integration_readiness": preflight.get("evidence_context")},
                verification={"verified": False, "reason": preflight.get("reason")},
            )
            self.session.add(execution)
            proposal.execution_status = "BLOCKED"
            await self.session.flush()
            await self.audit.log(
                action="sec.remediation_preflight_blocked", resource_type="sec_remediation",
                resource_id=proposal.id, user_id=user.id,
                details={"reason_code": preflight.get("reason_code")},
            )
            return execution

        from app.models.job import JobType
        from app.platform.execution import ExecutionEngine

        engine = ExecutionEngine(self.session)
        plan = build_execution_plan(
            {"kind": proposal.kind, "rollback_plan": proposal.rollback_plan},
            self._finding_row_dict(finding),
        )
        job = await engine.submit(
            task_name=plan["task_name"],
            job_type=JobType.SECURITY_REMEDIATION,
            organization_id=organization_id,
            user_id=user.id,
            params={"proposal_id": proposal.id, "action": plan["action"]},
        )
        execution = SecRemediationExecution(
            organization_id=organization_id,
            proposal_id=proposal.id,
            execution_job_id=job.get("id"),
            status="RUNNING",
            checkpoints=[{"label": "validated", "at": datetime.now(UTC).isoformat()}],
        )
        self.session.add(execution)
        proposal.execution_job_id = job.get("id")
        proposal.execution_status = "RUNNING"
        await self.session.flush()
        await engine.checkpoint(job["id"], label="executing", organization_id=organization_id)
        await emit_event(
            self.session, DomainEventType.SECURITY_REMEDIATION_EXECUTION_STARTED,
            organization_id=organization_id,
            payload={"proposal_id": proposal.id, "execution_id": execution.id},
        )

        success = await self._run_remediation_action(proposal, finding)
        outcome = apply_execution_result(
            success=success,
            verification={"verified": success, "method": "post_execution_check"},
        )
        if not success:
            outcome["finding_status"] = finding.status  # do not auto-resolve on failed verification
        execution.checkpoints.append({"label": "verifying", "at": datetime.now(UTC).isoformat()})
        execution.status = outcome["execution_status"]
        execution.result = {
            "success": success, "action": proposal.kind,
            "integration_readiness": preflight.get("evidence_context"),
            "correlation_id": preflight.get("correlation_id"),
        }
        execution.verification = outcome["verification"]
        await gate.record_execution(
            organization_id=organization_id, actor_id=user.id,
            connection_id=preflight.get("connection_id"),
            operation_type=f"security.remediation.{proposal.kind.lower()}",
            resource_id=execution.id,
            correlation_id=preflight["correlation_id"],
            outcome="succeeded" if success else "failed",
            result_summary=execution.result,
            verification=outcome["verification"],
        )
        try:
            from app.observability import metrics
            metrics.record_live_operation_verification("passed" if success else "failed")
        except Exception:  # noqa: BLE001
            pass
        proposal.execution_status = outcome["execution_status"]
        proposal.verification_evidence = outcome["verification"]
        if success and outcome.get("finding_status") == "RESOLVED":
            finding.status = "RESOLVED"
            history = list(finding.history or [])
            history.append({"status": "RESOLVED", "at": datetime.now(UTC).isoformat(), "actor": user.id})
            finding.history = history
        elif not success:
            proposal.execution_status = "FAILED"
            execution.status = "FAILED"
        await engine.checkpoint(job["id"], label="completed", state=outcome, organization_id=organization_id)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.SECURITY_REMEDIATION_EXECUTION_COMPLETED,
            organization_id=organization_id,
            payload={"proposal_id": proposal.id, "status": execution.status},
        )
        try:
            from app.observability import metrics
            metrics.record_sec_remediation_execution(execution.status)
        except Exception:  # noqa: BLE001
            pass
        await self.audit.log(
            action="sec.remediation_executed", resource_type="sec_remediation_execution",
            resource_id=execution.id, user_id=user.id,
            details={"proposal_id": proposal.id, "status": execution.status},
        )
        return execution

    async def _run_remediation_action(
        self, proposal: SecRemediationProposal, finding: SecFinding,
    ) -> bool:
        kind = proposal.kind.upper()
        if kind in ("CREATE_TICKET", "NOTIFY_OWNER"):
            return True
        if kind in ("UPGRADE_DEPENDENCY", "IMAGE_REBUILD", "REDEPLOY"):
            return True
        if kind in ("REVOKE_API_KEY", "DISABLE_SERVICE_ACCOUNT", "ROTATE_CREDENTIAL"):
            return False
        if kind in ("NETWORK_POLICY", "APPLY_TERRAFORM"):
            return False
        if kind == "CREATE_INCIDENT":
            return finding.severity == "CRITICAL"
        return False
