"""Production pilot readiness orchestration (Sprint 66A)."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError, NexoraException, NotFoundError, ValidationError
from app.integration_readiness.evidence import redact_text
from app.integration_readiness.live_gate import CONTROL_PLANE_CAPABILITIES, LiveMutationGate
from app.integration_readiness.preflight import make_idempotency_key
from app.control_plane.kubernetes import operations as k8s_ops
from app.models.integration_readiness import IntConnectionRegistry
from app.models.delivery import DeliveryEnvironment
from app.models.pilot import (
    PILOT_ALLOWED_ACTIONS,
    PilotApproval,
    PilotAssessment,
    PilotChecklistItem,
    PilotEnrollment,
    PilotLiveOperation,
    PilotScorecard,
)
from app.models.user import User
from app.pilot.operations import PILOT_MUTATION_ACTIONS, PILOT_OPERATION_CATALOG
from app.pilot.assessment_collectors import (
    build_baseline_snapshot,
    build_findings,
    collect_github_evidence,
    collect_kubernetes_evidence,
    collect_prometheus_evidence,
)
from app.observability.metrics import (
    observe_pilot_assessment_duration,
    observe_pilot_time_to_first_value,
    record_pilot_integration_connected,
    record_pilot_live_operation,
    record_pilot_readiness_score,
    set_pilot_organizations_total,
)
from app.platform.events import DomainEventType, emit_event
from app.platform.ga import DiagnosticsBundleService, SupportModeService
from app.repositories.audit import AuditLogRepository
from app.repositories.pilot import (
    PilotApprovalRepo,
    PilotAssessmentRepo,
    PilotChecklistRepo,
    PilotEnrollmentRepo,
    PilotLiveOperationRepo,
    PilotScorecardRepo,
    PilotStageRepo,
)
from app.schemas.pilot import (
    AssessmentRecommendation,
    ChecklistItemView,
    ExecutionReadinessView,
    LiveOperationListItemView,
    LiveOperationListView,
    LiveOperationView,
    OnboardingPathView,
    PilotAssessmentView,
    PilotContactsUpdate,
    PilotDiagnosticsView,
    PilotReadinessView,
    PilotScorecardView,
)
from app.services.integration_readiness import IntegrationReadinessService
from app.services.pilot_execution import PilotExecutionMixin
from app.tenancy.permissions import can_read_resources, can_write_resources
from app.pilot.paths import (
    PILOT_CHECKLIST_TEMPLATE,
    PILOT_ONBOARDING_PATHS,
    PILOT_TROUBLESHOOTING,
)

from app.pilot.launch_readiness import _PROVIDER_ALIASES
_PILOT_LIVE_PROVIDERS = ("KUBERNETES", "GITHUB", "PROMETHEUS")


class PilotService(PilotExecutionMixin):
    def __init__(self, session: AsyncSession):
        self.session = session
        self.enrollments = PilotEnrollmentRepo(session)
        self.checklist = PilotChecklistRepo(session)
        self.assessments = PilotAssessmentRepo(session)
        self.scorecards = PilotScorecardRepo(session)
        self.live_ops = PilotLiveOperationRepo(session)
        self.stages = PilotStageRepo(session)
        self.approvals = PilotApprovalRepo(session)
        self.audit = AuditLogRepository(session)
        self.readiness = IntegrationReadinessService(session)

    def _ensure_pilot_enabled(self, organization_id: str) -> None:
        if not getattr(settings, "PILOT_MODE_ENABLED", False):
            raise ForbiddenError("Pilot mode is not enabled for this deployment")
        if organization_id not in getattr(settings, "PILOT_ORGANIZATION_IDS", []):
            if getattr(settings, "PILOT_MODE_ALL_ORGS", True):
                return
            raise ForbiddenError("Pilot Center is not enabled for this organization")

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        self._ensure_pilot_enabled(org_context.requires_organization)
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        self._ensure_pilot_enabled(org_context.requires_organization)
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _get_or_create_enrollment(self, organization_id: str) -> PilotEnrollment:
        row = await self.enrollments.get_for_org(organization_id)
        if row:
            await self._seed_checklist(row)
            return row
        row = PilotEnrollment(organization_id=organization_id, status="DRAFT")
        self.session.add(row)
        await self.session.flush()
        await self._seed_checklist(row)
        set_pilot_organizations_total(1)
        await emit_event(
            self.session, DomainEventType.PILOT_STARTED,
            organization_id=organization_id, payload={"enrollment_id": row.id},
        )
        return row

    async def _seed_checklist(self, enrollment: PilotEnrollment) -> None:
        existing = {i.item_key for i in await self.checklist.list_for_enrollment(enrollment.id)}
        for item in PILOT_CHECKLIST_TEMPLATE:
            if item["item_key"] in existing:
                continue
            self.session.add(PilotChecklistItem(
                organization_id=enrollment.organization_id,
                enrollment_id=enrollment.id,
                section=item["section"],
                item_key=item["item_key"],
                title=item["title"],
            ))
        await self.session.flush()

    async def get_readiness(self, user: User, org_context: OrgContext) -> PilotReadinessView:
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        items = await self.checklist.list_for_enrollment(enrollment.id)
        completed = sum(1 for i in items if i.completed)
        blockers = [b for i in items for b in (i.blockers or [])]
        score = round(completed / len(items) * 100) if items else 0
        record_pilot_readiness_score(score)
        return PilotReadinessView(
            enrollment_id=enrollment.id,
            status=enrollment.status,
            readiness_score=score,
            completed_items=completed,
            total_items=len(items),
            blockers=blockers,
            checklist=[ChecklistItemView.model_validate(i) for i in items],
            live_operations_enabled=enrollment.live_operations_enabled,
            onboarding_path_id=enrollment.onboarding_path_id,
        )

    async def check_readiness(self, user: User, org_context: OrgContext) -> PilotReadinessView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        await self.readiness.sync_registry(organization_id)
        items = await self.checklist.list_for_enrollment(enrollment.id)
        now = datetime.now(UTC)

        async def _mark(key: str, *, completed: bool, evidence: dict | None = None, blockers: list | None = None):
            for item in items:
                if item.item_key == key:
                    item.completed = completed
                    item.evidence = evidence or {}
                    item.blockers = blockers or []
                    if completed:
                        item.completed_at = now

        await _mark("readiness_enabled", completed=getattr(settings, "INTEGRATION_READINESS_ENABLED", True))
        conns = await self.readiness.list_connections(user, org_context)
        connected = [c for c in conns if c.lifecycle_state in ("CONNECTED", "DEGRADED")]
        await _mark("integration_connected", completed=bool(connected), evidence={"count": len(connected)})
        live = [c for c in connected if c.provider_mode == "live"]
        await _mark("capabilities_validated", completed=bool(live), evidence={"live_count": len(live)})

        try:
            from app.platform.ga import InstallationService
            ga_run = await InstallationService(self.session).run_readiness(organization_id=organization_id)
            await _mark("audit_healthy", completed=(ga_run.readiness_score or 0) >= 50,
                        evidence={"ga_score": ga_run.readiness_score})
            await _mark("backup_verified", completed=any(
                c.get("name") == "storage" and c.get("ok") for c in (ga_run.checks or [])
            ))
        except Exception:  # noqa: BLE001
            await _mark("audit_healthy", completed=False, blockers=["GA readiness check unavailable"])

        envs = list((await self.session.execute(
            select(DeliveryEnvironment).where(DeliveryEnvironment.organization_id == organization_id)
        )).scalars().all())
        prod = [e for e in envs if (e.tier or "").upper() == "PRODUCTION"]
        await _mark("production_tagged", completed=bool(prod))

        if enrollment.contacts.get("support_contact"):
            await _mark("contacts_configured", completed=True)

        await self.session.flush()
        enrollment = await self._get_or_create_enrollment(organization_id)
        if enrollment.onboarding_path_id:
            await self._maybe_complete_stage(
                enrollment, "CONNECT", owner_id=user.id,
                evidence={"path_id": enrollment.onboarding_path_id},
                outcome="Integration path selected",
            )
        score = round(sum(1 for i in items if i.completed) / len(items) * 100) if items else 0
        await self._maybe_complete_stage(
            enrollment, "VALIDATE", owner_id=user.id,
            evidence={"readiness_score": score, "connected": len(connected)},
            outcome="Integration readiness validated",
        )
        await emit_event(
            self.session, DomainEventType.PILOT_READINESS_CHECKED,
            organization_id=organization_id, payload={"enrollment_id": enrollment.id},
        )
        return await self.get_readiness(user, org_context)

    async def list_onboarding_paths(self, user: User, org_context: OrgContext) -> list[OnboardingPathView]:
        self._ensure_read(user, org_context)
        return [OnboardingPathView(**p) for p in PILOT_ONBOARDING_PATHS.values()]

    async def start_onboarding_path(self, user: User, org_context: OrgContext, path_id: str) -> dict:
        organization_id = self._ensure_write(user, org_context)
        if path_id not in PILOT_ONBOARDING_PATHS:
            raise NotFoundError("OnboardingPath", path_id)
        enrollment = await self._get_or_create_enrollment(organization_id)
        enrollment.onboarding_path_id = path_id
        enrollment.status = "ONBOARDING"
        await self._seed_checklist(enrollment)
        if not enrollment.started_at:
            enrollment.started_at = datetime.now(UTC)
        await self._ensure_execution_started(enrollment)
        await self._maybe_complete_stage(
            enrollment, "CONNECT", owner_id=user.id,
            evidence={"path_id": path_id},
            outcome=f"Onboarding path {path_id} started",
        )
        await self.session.flush()
        path = PILOT_ONBOARDING_PATHS[path_id]
        record_pilot_integration_connected(path_id)
        await emit_event(
            self.session, DomainEventType.PILOT_INTEGRATION_CONNECTED,
            organization_id=organization_id, payload={"path_id": path_id},
        )
        return {"enrollment_id": enrollment.id, "path": path, "status": enrollment.status}

    async def _assert_stages_completed(self, enrollment: PilotEnrollment, *stage_keys: str) -> None:
        stages = {s.stage_key: s for s in await self.stages.list_for_enrollment(enrollment.id)}
        for key in stage_keys:
            stage = stages.get(key)
            if not stage or stage.status != "COMPLETED":
                raise ValidationError(f"Stage {key} must be completed before continuing")

    def _pick_live_connection(self, conns: list, provider: str, *, preferred_id: str | None = None):
        allowed = _PROVIDER_ALIASES.get(provider, frozenset({provider}))
        matches = [c for c in conns if c.provider_type in allowed]
        if preferred_id:
            for c in matches:
                if c.id == preferred_id:
                    return c
        live = [
            c for c in matches
            if c.lifecycle_state == "CONNECTED" and c.provider_mode == "live"
        ]
        if not live:
            return None
        return sorted(live, key=lambda c: c.last_validated_at or datetime.min.replace(tzinfo=UTC), reverse=True)[0]

    async def _resolve_registry_secret(self, registry_id: str, user: User, org_context: OrgContext) -> dict | None:
        organization_id = org_context.requires_organization
        row = await self.readiness._get_registry(organization_id, registry_id)
        return await self.readiness._resolve_secret(row, user, org_context)

    async def run_assessment(self, user: User, org_context: OrgContext) -> PilotAssessmentView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        await self._assert_stages_completed(enrollment, "CONNECT", "VALIDATE")
        started = time.monotonic()
        source_modes: dict[str, str] = {}
        summary: dict = {"findings": [], "gaps": []}
        recommendations: list[AssessmentRecommendation] = []
        audit_ids: list[str] = []

        await self.readiness.sync_registry(organization_id)
        conns = await self.readiness.list_connections(user, org_context)
        for c in conns:
            if c.provider_type in _PILOT_LIVE_PROVIDERS:
                source_modes[c.provider_type] = c.provider_mode

        summary["integration_health"] = {
            "total": len(conns),
            "connected": sum(1 for c in conns if c.lifecycle_state == "CONNECTED"),
            "source_mode": "live" if any(c.provider_mode == "live" for c in conns) else "offline",
        }

        namespace = getattr(settings, "PILOT_INTERNAL_K8S_NAMESPACE", "nexora-pilot")
        repository = getattr(settings, "PILOT_INTERNAL_GITHUB_REPO", "pilot-admin/pilot-test")
        preferred = {
            "KUBERNETES": getattr(settings, "PILOT_INTERNAL_K8S_REGISTRY_ID", None),
            "GITHUB": getattr(settings, "PILOT_INTERNAL_GITHUB_REGISTRY_ID", None),
            "PROMETHEUS": getattr(settings, "PILOT_INTERNAL_PROMETHEUS_REGISTRY_ID", None),
        }

        k8s_conn = self._pick_live_connection(conns, "KUBERNETES", preferred_id=preferred["KUBERNETES"])
        gh_conn = self._pick_live_connection(conns, "GITHUB", preferred_id=preferred["GITHUB"])
        prom_conn = self._pick_live_connection(conns, "PROMETHEUS", preferred_id=preferred["PROMETHEUS"])

        missing = [p for p, row in (("KUBERNETES", k8s_conn), ("GITHUB", gh_conn), ("PROMETHEUS", prom_conn)) if not row]
        if missing:
            raise ValidationError(
                f"Live CONNECTED integrations required for assessment: {', '.join(missing)}",
            )

        k8s_secret = await self._resolve_registry_secret(k8s_conn.id, user, org_context)
        gh_secret = await self._resolve_registry_secret(gh_conn.id, user, org_context)
        prom_cfg = await self._resolve_registry_secret(prom_conn.id, user, org_context) or {}

        k8s_secret = {**(k8s_secret or {}), "namespace": namespace}
        summary["kubernetes"] = await collect_kubernetes_evidence(k8s_secret, namespace=namespace) if k8s_secret.get("kubeconfig") else {"error": "credential_unresolved"}
        summary["github"] = await collect_github_evidence(gh_secret, repository=repository) if gh_secret and gh_secret.get("token") else {"error": "credential_unresolved"}
        if not prom_cfg.get("endpoint"):
            identity = (prom_conn.validation_metadata or {}).get("provider_identity") or {}
            prom_cfg["endpoint"] = identity.get("endpoint") or getattr(
                settings, "PILOT_INTERNAL_PROMETHEUS_ENDPOINT", "http://pilot-prometheus:9090",
            )
        summary["prometheus"] = (
            await collect_prometheus_evidence(prom_cfg, namespace=namespace)
            if prom_cfg.get("endpoint") else {"error": "endpoint_unresolved"}
        )

        findings = build_findings(
            kubernetes=summary.get("kubernetes"),
            github=summary.get("github"),
            prometheus=summary.get("prometheus"),
        )
        summary["findings"] = [f.to_dict() for f in findings]
        summary["gaps"] = sorted({g for f in findings for g in f.gaps})
        summary["connection_ids"] = {
            "KUBERNETES": k8s_conn.id,
            "GITHUB": gh_conn.id,
            "PROMETHEUS": prom_conn.id,
        }

        for f in findings:
            if f.recommendation and f.confidence != "INSUFFICIENT_EVIDENCE":
                recommendations.append(AssessmentRecommendation(
                    priority="HIGH" if f.risk in ("HIGH", "MEDIUM") else "LOW",
                    action=f.recommendation,
                    evidence=f.evidence,
                    source_mode=f.source_mode,
                ))
            elif f.gaps:
                recommendations.append(AssessmentRecommendation(
                    priority="MEDIUM",
                    action=f"Evidence gap: {f.title} — review {f.source} integration scope",
                    evidence=f.evidence,
                    source_mode=f.source_mode,
                ))

        if not recommendations:
            recommendations.append(AssessmentRecommendation(
                priority="LOW",
                action="Assessment captured with live read-only evidence; no elevated risks detected",
                evidence=[{"findings": len(findings)}],
                source_mode="live",
            ))

        duration_ms = int((time.monotonic() - started) * 1000)
        observe_pilot_assessment_duration(duration_ms / 1000.0)
        row = PilotAssessment(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            summary=summary,
            recommendations=[r.model_dump() for r in recommendations],
            source_modes=source_modes,
            duration_ms=duration_ms,
        )
        self.session.add(row)
        await self.session.flush()
        if enrollment.started_at:
            started_at = enrollment.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            created = row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            observe_pilot_time_to_first_value((created - started_at).total_seconds())
        evt = await emit_event(
            self.session, DomainEventType.PILOT_ASSESSMENT_COMPLETED,
            organization_id=organization_id, payload={"assessment_id": row.id},
        )
        if evt and getattr(evt, "id", None):
            audit_ids.append(evt.id)
        await self.audit.log(
            action="pilot.assessment.run",
            resource_type="pilot_assessment",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"source_modes": source_modes, "finding_count": len(findings)},
        )
        await self._complete_stage(
            enrollment, "READ_ONLY_ASSESSMENT", owner_id=user.id,
            evidence={"assessment_id": row.id, "source_modes": source_modes, "finding_count": len(findings)},
            outcome="Read-only assessment completed with live evidence",
        )
        md = self._assessment_markdown(row, recommendations, findings)
        return PilotAssessmentView(
            id=row.id, status=row.status, summary=summary,
            recommendations=recommendations, source_modes=source_modes,
            created_at=row.created_at, export_markdown=md,
        )

    @staticmethod
    def _assessment_markdown(
        row: PilotAssessment,
        recs: list[AssessmentRecommendation],
        findings: list | None = None,
    ) -> str:
        lines = ["# Pilot Read-Only Assessment\n", f"Assessment ID: {row.id}\n"]
        if findings:
            lines.append("## Findings\n")
            for f in findings[:10]:
                title = f.title if hasattr(f, "title") else f.get("title", "")
                risk = f.risk if hasattr(f, "risk") else f.get("risk", "")
                conf = f.confidence if hasattr(f, "confidence") else f.get("confidence", "")
                lines.append(f"- **{title}** (risk={risk}, confidence={conf})")
        lines.append("\n## Recommendations\n")
        for r in recs[:8]:
            lines.append(f"- **{r.priority}**: {r.action} _(source: {r.source_mode})_")
        return "\n".join(lines)

    async def get_assessment(self, user: User, org_context: OrgContext) -> PilotAssessmentView | None:
        organization_id = self._ensure_read(user, org_context)
        row = await self.assessments.latest(organization_id)
        if not row:
            return None
        recs = [AssessmentRecommendation(**r) for r in (row.recommendations or [])]
        findings = (row.summary or {}).get("findings") or []
        return PilotAssessmentView(
            id=row.id, status=row.status, summary=row.summary or {},
            recommendations=recs, source_modes=row.source_modes or {},
            created_at=row.created_at,
            export_markdown=self._assessment_markdown(row, recs, findings),
        )

    async def get_scorecard(self, user: User, org_context: OrgContext) -> PilotScorecardView:
        organization_id = self._ensure_read(user, org_context)
        row = await self.scorecards.latest(organization_id)
        if not row:
            return PilotScorecardView(scores={}, metrics={}, insufficient_data=["baseline_not_captured"], created_at=None)
        enrollment = await self._get_or_create_enrollment(organization_id)
        baseline = self._current_baseline_doc(enrollment.baseline)
        return PilotScorecardView(
            scores=row.scores or {},
            metrics={**(row.metrics or {}), "baseline_hash": baseline.get("hash")},
            insufficient_data=row.insufficient_data or [],
            created_at=row.created_at,
        )

    async def capture_baseline(self, user: User, org_context: OrgContext) -> PilotScorecardView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        await self._assert_stages_completed(enrollment, "CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT")
        assess = await self.assessments.latest(organization_id)
        if not assess:
            raise ValidationError("Run read-only assessment before capturing baseline")

        readiness = await self.get_readiness(user, org_context)
        conns = await self.readiness.list_connections(user, org_context)
        live_conns = [c for c in conns if c.provider_type in _PILOT_LIVE_PROVIDERS and c.lifecycle_state == "CONNECTED"]
        visibility = round(sum(1 for c in live_conns if c.lifecycle_state == "CONNECTED") / max(len(live_conns), 1) * 100) if live_conns else None
        automation = round(sum(1 for c in live_conns if c.provider_mode == "live") / max(len(live_conns), 1) * 100) if live_conns else None
        setup_score = readiness.readiness_score
        findings = (assess.summary or {}).get("findings") or []
        gaps = (assess.summary or {}).get("gaps") or []
        elevated = sum(1 for f in findings if f.get("risk") in ("HIGH", "MEDIUM"))
        risk = min(100, (automation or 0) + elevated * 5) if automation is not None else None

        insufficient: list[str] = list(gaps)
        if visibility is None:
            insufficient.append("visibility_score: connect integrations")

        scores = {
            "setup_readiness": setup_score,
            "visibility": visibility,
            "operational_maturity": visibility,
            "automation_readiness": automation,
            "risk": 100 - (risk or 0) if risk is not None else None,
            "value_realized": min(setup_score, visibility or 0) if visibility is not None else None,
        }
        metrics = {
            "integration_connection_success_rate": round(
                sum(1 for c in live_conns if c.lifecycle_state == "CONNECTED") / max(len(live_conns), 1), 2,
            ) if live_conns else None,
            "time_to_first_assessment_hours": None,
            "finding_count": len(findings),
            "insufficient_evidence_count": sum(
                1 for f in findings if f.get("confidence") == "INSUFFICIENT_EVIDENCE"
            ),
        }
        if enrollment.started_at and assess.created_at:
            started = enrollment.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            created = assess.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            metrics["time_to_first_assessment_hours"] = round((created - started).total_seconds() / 3600, 2)

        captured_at = datetime.now(UTC).isoformat()
        integration_health = [
            {
                "provider": c.provider_type,
                "lifecycle_state": c.lifecycle_state,
                "provider_mode": c.provider_mode,
                "last_validated_at": c.last_validated_at.isoformat() if c.last_validated_at else None,
            }
            for c in live_conns
        ]
        baseline_body = build_baseline_snapshot(
            assessment_summary=assess.summary or {},
            integration_health=integration_health,
            captured_at=captured_at,
        )
        baseline_hash = hashlib.sha256(
            json.dumps(baseline_body, sort_keys=True, default=str).encode(),
        ).hexdigest()
        baseline_body["hash"] = baseline_hash
        baseline_body["assessment_id"] = assess.id

        row = PilotScorecard(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            scores=scores,
            metrics={**metrics, "baseline_hash": baseline_hash},
            insufficient_data=sorted(set(insufficient)),
        )
        self.session.add(row)
        enrollment.baseline = self._store_baseline_with_history(enrollment.baseline, baseline_body)
        await self.session.flush()

        await emit_event(
            self.session, DomainEventType.PILOT_BASELINE_CAPTURED,
            organization_id=organization_id, payload={"scorecard_id": row.id, "baseline_hash": baseline_hash},
        )
        await self.audit.log(
            action="pilot.baseline.capture",
            resource_type="pilot_scorecard",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"baseline_hash": baseline_hash, "assessment_id": assess.id},
        )
        await self._complete_stage(
            enrollment, "BASELINE_CAPTURE", owner_id=user.id,
            evidence={"scorecard_id": row.id, "baseline_hash": baseline_hash, "assessment_id": assess.id},
            outcome="Pilot baseline captured from live assessment",
        )
        await self.session.flush()
        return PilotScorecardView(
            scores=scores,
            metrics={**metrics, "baseline_hash": baseline_hash},
            insufficient_data=sorted(set(insufficient)),
            created_at=row.created_at,
        )

    @staticmethod
    def _current_baseline_doc(baseline: dict | None) -> dict:
        if not baseline:
            return {}
        if isinstance(baseline.get("current"), dict):
            return baseline["current"]
        return baseline

    @staticmethod
    def _store_baseline_with_history(existing: dict | None, new_body: dict) -> dict:
        prior = PilotService._current_baseline_doc(existing)
        history: list[dict] = []
        if existing and isinstance(existing.get("history"), list):
            history = list(existing["history"])
        if prior.get("hash"):
            history.append({
                "hash": prior.get("hash"),
                "captured_at": prior.get("captured_at"),
                "assessment_id": prior.get("assessment_id"),
            })
        return {"current": new_body, "history": history}

    async def refresh_baseline(self, user: User, org_context: OrgContext) -> PilotScorecardView:
        """Capture a new baseline snapshot without advancing pilot stages."""
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        assess = await self.assessments.latest(organization_id)
        if not assess:
            raise ValidationError("Run read-only assessment before refreshing baseline")

        readiness = await self.get_readiness(user, org_context)
        conns = await self.readiness.list_connections(user, org_context)
        live_conns = [c for c in conns if c.provider_type in _PILOT_LIVE_PROVIDERS and c.lifecycle_state == "CONNECTED"]
        visibility = round(sum(1 for c in live_conns if c.lifecycle_state == "CONNECTED") / max(len(live_conns), 1) * 100) if live_conns else None
        automation = round(sum(1 for c in live_conns if c.provider_mode == "live") / max(len(live_conns), 1) * 100) if live_conns else None
        setup_score = readiness.readiness_score
        findings = (assess.summary or {}).get("findings") or []
        gaps = (assess.summary or {}).get("gaps") or []
        elevated = sum(1 for f in findings if f.get("risk") in ("HIGH", "MEDIUM"))
        risk = min(100, (automation or 0) + elevated * 5) if automation is not None else None
        insufficient: list[str] = list(gaps)
        if visibility is None:
            insufficient.append("visibility_score: connect integrations")

        scores = {
            "setup_readiness": setup_score,
            "visibility": visibility,
            "operational_maturity": visibility,
            "automation_readiness": automation,
            "risk": 100 - (risk or 0) if risk is not None else None,
            "value_realized": min(setup_score, visibility or 0) if visibility is not None else None,
        }
        metrics = {
            "integration_connection_success_rate": round(
                sum(1 for c in live_conns if c.lifecycle_state == "CONNECTED") / max(len(live_conns), 1), 2,
            ) if live_conns else None,
            "finding_count": len(findings),
            "insufficient_evidence_count": sum(
                1 for f in findings if f.get("confidence") == "INSUFFICIENT_EVIDENCE"
            ),
        }
        captured_at = datetime.now(UTC).isoformat()
        integration_health = [
            {
                "provider": c.provider_type,
                "lifecycle_state": c.lifecycle_state,
                "provider_mode": c.provider_mode,
                "last_validated_at": c.last_validated_at.isoformat() if c.last_validated_at else None,
            }
            for c in live_conns
        ]
        baseline_body = build_baseline_snapshot(
            assessment_summary=assess.summary or {},
            integration_health=integration_health,
            captured_at=captured_at,
        )
        baseline_hash = hashlib.sha256(
            json.dumps(baseline_body, sort_keys=True, default=str).encode(),
        ).hexdigest()
        baseline_body["hash"] = baseline_hash
        baseline_body["assessment_id"] = assess.id

        row = PilotScorecard(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            scores=scores,
            metrics={**metrics, "baseline_hash": baseline_hash},
            insufficient_data=sorted(set(insufficient)),
        )
        self.session.add(row)
        enrollment.baseline = self._store_baseline_with_history(enrollment.baseline, baseline_body)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.PILOT_BASELINE_CAPTURED,
            organization_id=organization_id,
            payload={"scorecard_id": row.id, "baseline_hash": baseline_hash, "refresh": True},
        )
        await self.audit.log(
            action="pilot.baseline.refresh",
            resource_type="pilot_scorecard",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"baseline_hash": baseline_hash, "assessment_id": assess.id},
        )
        await self.session.flush()
        return PilotScorecardView(
            scores=scores,
            metrics={**metrics, "baseline_hash": baseline_hash},
            insufficient_data=sorted(set(insufficient)),
            created_at=row.created_at,
        )

    async def enable_live_operations(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        readiness = await self.get_readiness(user, org_context)
        stages = await self.stages.list_for_enrollment(enrollment.id)
        baseline_captured = any(
            s.stage_key == "BASELINE_CAPTURE" and s.status == "COMPLETED" for s in stages
        )
        if readiness.readiness_score < 60 and not baseline_captured:
            raise ValidationError("Pilot readiness score must be at least 60 before enabling live operations")
        enrollment.live_operations_enabled = True
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.PILOT_LIVE_OPERATION_ENABLED,
            organization_id=organization_id, payload={"enrollment_id": enrollment.id},
        )
        return {"live_operations_enabled": True, "enrollment_id": enrollment.id}

    async def propose_live_operation(
        self, user: User, org_context: OrgContext, *, action: str, resource_name: str,
        environment_id: str, cluster_id: str | None = None, params: dict | None = None,
        template_id: str | None = None, rollback_plan: str | None = None,
        namespace: str | None = None, idempotency_key: str | None = None,
    ) -> LiveOperationView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        if not enrollment.live_operations_enabled:
            raise ValidationError("Enable pilot live operations before proposing mutations")
        if action not in PILOT_ALLOWED_ACTIONS:
            raise ValidationError(f"Action '{action}' is not allowed in pilot mode")
        if template_id and template_id not in PILOT_OPERATION_CATALOG:
            raise ValidationError(f"Unknown operation template '{template_id}'")
        existing = list((await self.session.execute(
            select(PilotLiveOperation).where(
                PilotLiveOperation.organization_id == organization_id,
                PilotLiveOperation.status.notin_(("CANCELLED", "FAILED")),
            )
        )).scalars().all())
        if existing:
            raise ValidationError("An active pilot operation proposal already exists for this organization")
        op = await self._propose_with_safety(
            enrollment, user, organization_id,
            action=action,
            template_id=template_id,
            resource_name=resource_name,
            environment_id=environment_id,
            cluster_id=cluster_id,
            params=params,
            rollback_plan=rollback_plan,
            namespace=namespace,
            idempotency_key=idempotency_key,
        )
        token = getattr(op, "_confirmation_token_plain", None)
        return LiveOperationView(
            id=op.id, action=action, resource_name=resource_name, status=op.status,
            confirmation_token=token,
            preflight=op.preflight or {},
            correlation_id=op.correlation_id,
            source_mode=op.source_mode,
            payload_hash=op.payload_hash,
            execution_label=(op.preflight or {}).get("execution_label"),
            template_id=op.template_id,
            environment_id=op.environment_id,
            cluster_id=op.cluster_id,
            params=op.params or {},
            rollback_plan=op.rollback_plan,
        )

    async def list_live_operations(
        self, user: User, org_context: OrgContext,
    ) -> LiveOperationListView:
        """Read-only list of all pilot live operations for the active organization."""
        from app.pilot.customer_portal import operator_execution_console_label

        organization_id = self._ensure_read(user, org_context)
        ops = await self.live_ops.list_for_org(organization_id, limit=100)
        approval_ids = [op.approval_id for op in ops if op.approval_id]
        approvals_by_id: dict[str, PilotApproval] = {}
        if approval_ids:
            rows = list((await self.session.execute(
                select(PilotApproval).where(PilotApproval.id.in_(approval_ids)),
            )).scalars().all())
            approvals_by_id = {row.id: row for row in rows}
        items = []
        for op in ops:
            approval = approvals_by_id.get(op.approval_id) if op.approval_id else None
            approval_status = approval.status if approval else None
            items.append(LiveOperationListItemView(
                id=op.id,
                action=op.action,
                resource_name=op.resource_name,
                status=op.status,
                verification_status=op.verification_status,
                approval_status=approval_status,
                operator_label=operator_execution_console_label(op.status, approval_status),
                created_at=op.created_at,
            ))
        return LiveOperationListView(items=items)

    async def get_live_operation(
        self, user: User, org_context: OrgContext, operation_id: str,
    ) -> LiveOperationView:
        organization_id = self._ensure_read(user, org_context)
        op = await self.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        return LiveOperationView(
            id=op.id,
            action=op.action,
            resource_name=op.resource_name,
            status=op.status,
            preflight=op.preflight or {},
            result=op.result or {},
            verification=op.verification or {},
            correlation_id=op.correlation_id,
            source_mode=op.source_mode,
            verification_status=op.verification_status,
            payload_hash=op.payload_hash,
            execution_label=(op.preflight or {}).get("execution_label"),
            template_id=op.template_id,
            environment_id=op.environment_id,
            cluster_id=op.cluster_id,
            params=op.params or {},
            rollback_plan=op.rollback_plan,
        )

    async def check_execution_readiness(
        self, user: User, org_context: OrgContext, operation_id: str,
    ) -> ExecutionReadinessView:
        """Read-only pre-execution validation without typed confirmation or provider mutation."""
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        op = await self.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)

        gates: dict = {}
        blockers: list[str] = []

        stages = {s.stage_key: s.status for s in await self.stages.list_for_enrollment(enrollment.id)}
        for key in (
            "CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT",
            "BASELINE_CAPTURE", "PROPOSE_OPERATION", "CUSTOMER_APPROVAL",
        ):
            ok = stages.get(key) == "COMPLETED"
            gates[f"stage_{key.lower()}"] = ok
            if not ok:
                blockers.append(f"Stage {key} not completed")

        gates["typed_confirmation_supplied"] = False
        gates["typed_confirmation_required"] = True

        approval_valid = False
        try:
            approval = await self._validate_approval(op, organization_id)
            approval_valid = True
            gates["approval_approved"] = True
            gates["approval_unexpired"] = True
            gates["payload_hash_matches"] = approval.payload_hash == op.payload_hash
        except ValidationError as exc:
            gates["approval_approved"] = False
            blockers.append(str(exc))

        gates["kill_switch_off"] = not enrollment.kill_switch
        if enrollment.kill_switch:
            blockers.append("Pilot kill switch is active")

        gates["operation_limit_ok"] = enrollment.operation_count < enrollment.operation_limit
        if not gates["operation_limit_ok"]:
            blockers.append("Pilot operation limit reached for this enrollment")

        cooldown_clear = True
        if enrollment.last_mutation_at:
            last = enrollment.last_mutation_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            cooldown = timedelta(minutes=enrollment.cooldown_minutes or 30)
            cooldown_clear = datetime.now(UTC) - last >= cooldown
        gates["cooldown_clear"] = cooldown_clear
        if not cooldown_clear:
            blockers.append("Mutation cooldown active")

        env = await self.session.get(DeliveryEnvironment, op.environment_id)
        gates["non_production_environment"] = bool(
            env and (env.tier or "").upper() not in ("PRODUCTION", "PROD"),
        )
        if not gates["non_production_environment"]:
            blockers.append("Production environment not permitted")

        gates["operation_awaiting_confirmation"] = op.status == "PENDING_CONFIRMATION"
        if op.status != "PENDING_CONFIRMATION":
            blockers.append(f"Operation status must be PENDING_CONFIRMATION (got {op.status})")

        gates["idempotency_key_present"] = bool(op.correlation_id)
        gates["idempotency_unused"] = op.status not in (
            "EXECUTING", "PENDING_VERIFICATION", "SUCCEEDED", "FAILED",
        )
        if not op.correlation_id:
            blockers.append("Idempotency key missing on operation")

        gates["rollback_plan_present"] = bool(op.rollback_plan)
        gates["before_state_captured"] = bool(op.before_state)
        if not op.before_state:
            blockers.append("Before-state evidence not captured")

        template = PILOT_OPERATION_CATALOG.get(op.template_id or "")
        gates["verification_plan_defined"] = bool(
            template.get("verification_signals") or (op.params or {}).get("verification_criteria"),
        )

        gate = LiveMutationGate(self.session)
        required = template.get("required_capabilities") if template else CONTROL_PLANE_CAPABILITIES.get(
            op.action, ["kubernetes.workloads.write"],
        )
        registry_id = op.cluster_id or getattr(settings, "PILOT_INTERNAL_K8S_REGISTRY_ID", None)
        resolved = await gate._resolve_registry(
            organization_id,
            integration_connection_id=registry_id,
            credential_id=None,
            resource_lookup=("marketplace", op.cluster_id) if op.cluster_id else None,
        )
        if resolved is None:
            for row in await gate.registry.list_for_org(organization_id):
                if row.provider_type == "KUBERNETES" and row.lifecycle_state in ("CONNECTED", "DEGRADED"):
                    resolved = row
                    break

        gates["integration_connected"] = resolved is not None and resolved.lifecycle_state in (
            "CONNECTED", "DEGRADED",
        )
        gates["provider_mode_live"] = resolved is not None and (resolved.provider_mode or "").lower() == "live"
        if not gates["integration_connected"]:
            blockers.append("Kubernetes integration is not connected")
        if not gates["provider_mode_live"]:
            blockers.append("Provider mode must be live")

        integration_id = resolved.id if resolved else registry_id
        ns = (op.params or {}).get("namespace", "default")
        preflight = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=integration_id,
            operation_type=f"pilot.{op.action}",
            resource_type="kubernetes_deployment",
            resource_id=f"{ns}/{op.resource_name}",
            environment_id=op.environment_id,
            idempotency_key=op.correlation_id or make_idempotency_key(
                org_id=organization_id, operation=op.action, target_id=op.id,
            ),
            required_capabilities=required,
            approval_satisfied=True,
            explicit_simulation=False,
        )
        gates["live_mutation_gate_preflight"] = preflight.get("allowed", False)
        if not preflight.get("allowed"):
            blockers.append(preflight.get("reason") or "Live mutation gate preflight blocked")

        target_replicas = (op.params or {}).get("replicas")
        from_replicas = (op.params or {}).get("from_replicas")
        gates["target_replicas_defined"] = target_replicas is not None
        gates["rollback_target_valid"] = bool(op.rollback_plan) and from_replicas is not None

        execution_label = (op.preflight or {}).get("execution_label") or "LIVE-ELIGIBLE / NOT EXECUTED"
        ready = (
            approval_valid
            and not blockers
            and preflight.get("allowed")
            and gates["operation_awaiting_confirmation"]
        )

        return ExecutionReadinessView(
            operation_id=operation_id,
            operation_status=op.status,
            ready_for_typed_confirmation=ready,
            provider_mutation_called=False,
            kubernetes_mutation_called=False,
            remaining_required_action="typed confirmation",
            execution_label=execution_label,
            gates=gates,
            blockers=blockers,
            preflight=preflight,
        )

    async def get_operator_handoff(
        self, user: User, org_context: OrgContext, operation_id: str,
    ) -> dict:
        """Read-only operator handoff — re-runs readiness checks at retrieval time."""
        from app.pilot.approval_package import verification_checklist_markdown
        from app.pilot.customer_portal import operator_handoff_label, sanitize_customer_view
        from app.pilot.launch_readiness import integration_freshness_ok
        from app.models.customer_pilot import PilotApprovalPackage
        from sqlalchemy import select

        organization_id = self._ensure_read(user, org_context)
        readiness = await self.check_execution_readiness(user, org_context, operation_id)
        op = await self.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)

        approval = None
        if op.approval_id:
            approval = await self.approvals.get_for_org(op.approval_id, organization_id)

        pkg_row = (await self.session.execute(
            select(PilotApprovalPackage).where(
                PilotApprovalPackage.operation_id == operation_id,
                PilotApprovalPackage.organization_id == organization_id,
            ).order_by(PilotApprovalPackage.created_at.desc()).limit(1),
        )).scalar_one_or_none()

        integrations = []
        for conn in await self.readiness.list_connections(user, org_context):
            integrations.append({
                "provider_type": conn.provider_type,
                "lifecycle_state": conn.lifecycle_state,
                "provider_mode": conn.provider_mode,
                "fresh": integration_freshness_ok(conn.last_validated_at),
            })

        checklist = []
        if pkg_row and pkg_row.package:
            checklist = [
                line.lstrip("- [ ] ").strip()
                for line in verification_checklist_markdown(pkg_row.package).splitlines()
                if line.strip().startswith("- [ ]")
            ]

        handoff_status = operator_handoff_label(readiness.blockers, readiness.model_dump())

        return sanitize_customer_view({
            "operation_id": operation_id,
            "handoff_status": handoff_status,
            "customer_approval": {
                "id": approval.id if approval else None,
                "status": approval.status if approval else None,
                "approver_name": approval.approver_name if approval else None,
                "approver_email": approval.approver_email if approval else None,
                "payload_hash": approval.payload_hash if approval else None,
                "expires_at": approval.expires_at.isoformat() if approval and approval.expires_at else None,
            },
            "operation": {
                "action": op.action,
                "resource_name": op.resource_name,
                "status": op.status,
                "params": op.params or {},
            },
            "rollback_plan": op.rollback_plan,
            "integration_readiness": integrations,
            "before_state": op.before_state or {},
            "typed_confirmation_text": op.resource_name,
            "verification_checklist": checklist,
            "gates": readiness.gates,
            "blockers": readiness.blockers,
            "ready_for_operator_confirmation": readiness.ready_for_typed_confirmation,
            "read_only": True,
        })

    async def confirm_live_operation(
        self, user: User, org_context: OrgContext, operation_id: str, *,
        confirmation_token: str, typed_confirmation: str, approved: bool = True,
    ) -> LiveOperationView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        op = await self.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        if op.status not in ("PENDING_CONFIRMATION",):
            raise NexoraException("Operation already confirmed or completed", 409)
        if enrollment.kill_switch:
            raise ValidationError("Pilot kill switch is active — all operations are blocked")
        if not approved:
            op.status = "CANCELLED"
            await self.session.flush()
            return LiveOperationView(id=op.id, action=op.action, resource_name=op.resource_name, status=op.status)
        if typed_confirmation != op.resource_name:
            raise ValidationError("Typed confirmation must exactly match the resource name")
        op.typed_confirmation = typed_confirmation
        token_hash = hashlib.sha256(confirmation_token.encode()).hexdigest()[:64]
        if token_hash != op.confirmation_token:
            raise ValidationError("Invalid confirmation token")
        await self._validate_approval(op, organization_id)

        gate = LiveMutationGate(self.session)
        template = PILOT_OPERATION_CATALOG.get(op.template_id or "")
        required = template.get("required_capabilities") if template else CONTROL_PLANE_CAPABILITIES.get(
            op.action, ["kubernetes.workloads.write"],
        )
        registry_id = op.cluster_id or getattr(settings, "PILOT_INTERNAL_K8S_REGISTRY_ID", None)
        resolved = await gate._resolve_registry(
            organization_id,
            integration_connection_id=registry_id,
            credential_id=None,
            resource_lookup=("marketplace", op.cluster_id) if op.cluster_id else None,
        )
        if resolved is None:
            for row in await gate.registry.list_for_org(organization_id):
                if row.provider_type == "KUBERNETES" and row.lifecycle_state in ("CONNECTED", "DEGRADED"):
                    resolved = row
                    break
        if resolved is None:
            raise ValidationError("Kubernetes integration is not connected for pilot execution")
        preflight = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=resolved.id,
            operation_type=f"pilot.{op.action}",
            resource_type="pilot_live_operation",
            resource_id=op.id,
            environment_id=op.environment_id,
            idempotency_key=op.correlation_id or make_idempotency_key(
                org_id=organization_id, operation=op.action, target_id=op.id,
            ),
            required_capabilities=required,
            approval_satisfied=True,
            explicit_simulation=False,
        )
        source_mode = self._resolve_source_mode(preflight)
        op.source_mode = source_mode
        if not preflight["allowed"]:
            record_pilot_live_operation("blocked")
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id, payload={"operation_id": op.id},
            )
            await self.session.flush()
            raise ValidationError(preflight.get("reason") or "Live mutation gate blocked execution")

        op.status = "EXECUTING"
        op.confirmed_at = datetime.now(UTC)
        op.approved_by = user.id
        op.correlation_id = preflight["correlation_id"]
        op.preflight = preflight.get("evidence_context") or {}

        if preflight.get("simulated"):
            op.result = {"simulated": True, "action": op.action, "message": "Explicit simulation — no live mutation"}
            op.source_mode = "SIMULATED"
            op.status = "PENDING_VERIFICATION"
        else:
            conn_id = preflight.get("connection_id") or resolved.id
            registry_row = await self.session.get(IntConnectionRegistry, conn_id)
            secret = (
                await self.readiness._resolve_secret(registry_row, user, org_context)
                if registry_row else None
            )
            write_params = dict(op.params or {})
            write_params.setdefault("namespace", "default")
            write_params["name"] = op.resource_name
            exec_result = await k8s_ops.execute_write(
                secret or {},
                op.action,
                write_params,
                explicit_simulation=False,
            )
            exec_result = {
                **exec_result,
                "integration_readiness": preflight.get("evidence_context"),
                "correlation_id": preflight["correlation_id"],
                "execution_path": "pilot.confirm_live_operation→LiveMutationGate→k8s_ops.execute_write",
                "nexora_controlled": True,
            }
            op.result = exec_result
            op.source_mode = "LIVE"
            if exec_result.get("blocked") or exec_result.get("success") is False:
                op.status = "FAILED"
                enrollment.execution_status = "FAILED"
            else:
                op.status = "PENDING_VERIFICATION"

        op.completed_at = datetime.now(UTC)
        if op.action in PILOT_MUTATION_ACTIONS and op.status != "FAILED":
            enrollment.operation_count += 1
            enrollment.last_mutation_at = datetime.now(UTC)
        exec_outcome = "failed" if op.status == "FAILED" else "succeeded"
        await gate.record_execution(
            organization_id=organization_id, actor_id=user.id,
            connection_id=preflight.get("connection_id"),
            operation_type=f"pilot.{op.action}", resource_id=op.id,
            correlation_id=preflight["correlation_id"],
            outcome="started",
            result_summary=op.result, verification=op.verification,
        )
        if exec_outcome == "succeeded":
            await gate.record_execution(
                organization_id=organization_id, actor_id=user.id,
                connection_id=preflight.get("connection_id"),
                operation_type=f"pilot.{op.action}", resource_id=op.id,
                correlation_id=preflight["correlation_id"],
                outcome="succeeded",
                result_summary=op.result,
            )
        else:
            await gate.record_execution(
                organization_id=organization_id, actor_id=user.id,
                connection_id=preflight.get("connection_id"),
                operation_type=f"pilot.{op.action}", resource_id=op.id,
                correlation_id=preflight["correlation_id"],
                outcome="failed",
                result_summary=op.result,
            )
        await self._maybe_complete_stage(
            enrollment, "EXECUTE", owner_id=user.id,
            evidence={
                "operation_id": op.id,
                "source_mode": op.source_mode,
                "execution_path": (op.result or {}).get("execution_path"),
            },
            rollback_plan=op.rollback_plan,
            outcome=f"Executed {op.action}",
            failed=op.status == "FAILED",
        )
        await emit_event(
            self.session, DomainEventType.PILOT_LIVE_OPERATION_CONFIRMED,
            organization_id=organization_id, payload={"operation_id": op.id, "source_mode": op.source_mode},
        )
        record_pilot_live_operation(op.status.lower())
        await self.audit.log(
            action="pilot.live_operation_confirmed", resource_type="pilot_live_operation",
            resource_id=op.id, user_id=user.id, organization_id=organization_id,
            details={
                "action": op.action,
                "status": op.status,
                "source_mode": op.source_mode,
                "execution_path": (op.result or {}).get("execution_path"),
                "nexora_controlled": (op.result or {}).get("nexora_controlled", False),
            },
        )
        await self.session.flush()
        if preflight.get("simulated"):
            verified = await self.verify_live_operation(
                user, org_context, op.id, advance_complete=False,
            )
            return verified
        return LiveOperationView(
            id=op.id, action=op.action, resource_name=op.resource_name,
            status=op.status, preflight=op.preflight, result=op.result or {},
            source_mode=op.source_mode, correlation_id=op.correlation_id,
            payload_hash=op.payload_hash,
            execution_label=(op.preflight or {}).get("execution_label"),
            verification_status=op.verification_status,
        )

    async def update_contacts(
        self, user: User, org_context: OrgContext, payload: PilotContactsUpdate,
    ) -> dict:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        contacts = dict(enrollment.contacts or {})
        if payload.support_contact is not None:
            contacts["support_contact"] = payload.support_contact
        if payload.escalation_contact is not None:
            contacts["escalation_contact"] = payload.escalation_contact
        if payload.approval_contact is not None:
            contacts["approval_contact"] = payload.approval_contact
        if payload.approver_email is not None:
            contacts["approver_email"] = payload.approver_email
        if payload.nexora_operator is not None:
            contacts["nexora_operator"] = payload.nexora_operator
        if payload.backup_restore_acknowledged is not None:
            contacts["backup_restore_acknowledged"] = payload.backup_restore_acknowledged
        enrollment.contacts = contacts
        await self.session.flush()
        return {"contacts": contacts}

    async def get_diagnostics(self, user: User, org_context: OrgContext) -> PilotDiagnosticsView:
        organization_id = self._ensure_read(user, org_context)
        dash = await self.readiness.get_dashboard(user, org_context)
        history: list[dict] = []
        conns = await self.readiness.list_connections(user, org_context)
        for c in conns[:10]:
            hist = await self.readiness.get_history(user, org_context, c.id)
            history.append({"connection_id": c.id, "entries": len(hist)})

        support_available = getattr(settings, "GA_READINESS_ENABLED", False)

        from app.pilot.operations_readiness import evaluate_pilot_operations_readiness
        from app.services.pilot_notification_delivery import PilotNotificationDeliveryService
        from app.services.pilot_operations import PilotOperationsService

        ops_svc = PilotOperationsService(self.session)
        ops_payload = await ops_svc.gather_operations_payload()
        ops_result = evaluate_pilot_operations_readiness(ops_payload)
        delivery_stats = await PilotNotificationDeliveryService(self.session).delivery_stats(organization_id)

        return PilotDiagnosticsView(
            integration_health=[
                {"provider": g.get("provider"), "missing": g.get("missing")}
                for g in (dash.capability_gaps or [])
            ],
            capability_gaps=dash.capability_gaps or [],
            validation_history=history,
            troubleshooting=PILOT_TROUBLESHOOTING,
            support_token_available=support_available,
            operations_readiness={
                "verdict": ops_result.get("verdict"),
                "failed_checks": ops_result.get("failed_checks"),
                "remediation_steps": ops_result.get("remediation_steps"),
            },
            notification_health=delivery_stats,
        )

    async def export_report(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        readiness = await self.get_readiness(user, org_context)
        assessment = await self.get_assessment(user, org_context)
        scorecard = await self.get_scorecard(user, org_context)
        execution = await self.get_execution_status(user, org_context)
        bundle = None
        if getattr(settings, "GA_READINESS_ENABLED", False):
            try:
                bundle = await DiagnosticsBundleService(self.session).collect(organization_id=organization_id)
            except Exception:  # noqa: BLE001
                bundle = None
        await emit_event(
            self.session, DomainEventType.PILOT_SUPPORT_BUNDLE_GENERATED,
            organization_id=organization_id, payload={"type": "pilot_report"},
        )
        return {
            "readiness": readiness.model_dump(),
            "assessment": assessment.model_dump() if assessment else None,
            "scorecard": scorecard.model_dump(),
            "execution": execution.model_dump(),
            "diagnostics_bundle": bundle,
            "exported_at": datetime.now(UTC).isoformat(),
        }

    async def get_launch_readiness(self, user: User, org_context: OrgContext) -> dict:
        """Read-only customer pilot launch evaluator — no mutations."""
        from app.pilot.launch_readiness import evaluate_customer_launch_readiness, integration_freshness_ok

        organization_id = self._ensure_read(user, org_context)
        org_allowed = (
            getattr(settings, "PILOT_MODE_ALL_ORGS", True)
            or organization_id in getattr(settings, "PILOT_ORGANIZATION_IDS", [])
        )
        enrollment_row = await self.enrollments.get_for_org(organization_id)
        enrollment = {
            "id": enrollment_row.id if enrollment_row else None,
            "status": enrollment_row.status if enrollment_row else None,
            "kill_switch": enrollment_row.kill_switch if enrollment_row else False,
            "operation_limit": enrollment_row.operation_limit if enrollment_row else None,
            "operation_count": enrollment_row.operation_count if enrollment_row else 0,
            "contacts": enrollment_row.contacts if enrollment_row else {},
        } if enrollment_row else {}

        conns = await self.readiness.list_connections(user, org_context)
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
            select(DeliveryEnvironment).where(DeliveryEnvironment.organization_id == organization_id)
        )).scalars().all())

        payload = {
            "pilot_mode_enabled": getattr(settings, "PILOT_MODE_ENABLED", False),
            "org_allowlisted": org_allowed,
            "enrollment": enrollment,
            "integrations": integrations,
            "environments": [{"id": e.id, "name": e.name, "tier": e.tier} for e in envs],
            "contacts": enrollment.get("contacts") or {},
            "backup_restore_documented": bool((enrollment.get("contacts") or {}).get("backup_restore_acknowledged")),
        }
        return evaluate_customer_launch_readiness(payload)

    async def issue_support_token(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_write(user, org_context)
        if not getattr(settings, "GA_READINESS_ENABLED", False):
            raise ValidationError("Support token flow requires GA readiness")
        svc = SupportModeService(self.session)
        token = await svc.issue_token(organization_id=organization_id, created_by=user.id, read_only=True)
        return token
