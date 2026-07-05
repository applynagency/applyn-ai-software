"""GitOps Progressive Delivery & Release Reliability orchestration (Sprint 65F).

Composes Delivery, Observability, Security, and Incident Response — does not duplicate engines.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException, NotFoundError
from app.core.logging import get_logger
from app.delivery.types import DeliveryOperationKind
from app.models.release_reliability import (
    RrFreezeWindow,
    RrHealthGateResult,
    RrPromotionPolicy,
    RrPromotionRequest,
    RrReleaseReliability,
    RrRollbackRecord,
    RrRolloutOperation,
    RrVerificationRun,
)
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.integration_readiness.observability_signals import collect_observability_signals
from app.integration_readiness.live_gate import LiveMutationGate
from app.integration_readiness.preflight import make_idempotency_key
from app.release_reliability.analytics import compute_release_analytics
from app.release_reliability.health_gates import evaluate_health_gate
from app.release_reliability.promotion import DEFAULT_POLICIES, evaluate_promotion, is_freeze_active
from app.release_reliability.rollback import apply_rollback_result, recommend_rollback
from app.release_reliability.rollout import (
    abort_rollout,
    detect_provider_mode,
    inspect_rollout,
    pause_rollout,
    promote_rollout,
    propose_rollout,
    resume_rollout,
    rollback_rollout,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.delivery import (
    DeliveryArtifactRepository,
    DeliveryDeploymentRepository,
    DeliveryEnvironmentRepository,
    DeliveryReleaseRepository,
)
from app.repositories.release_reliability import (
    RrFreezeWindowRepo,
    RrHealthGateRepo,
    RrPromotionPolicyRepo,
    RrPromotionRequestRepo,
    RrReleaseRepo,
    RrRollbackRepo,
    RrRolloutRepo,
    RrVerificationRepo,
)
from app.schemas.delivery import OperationCreate
from app.schemas.release_reliability import (
    FreezeWindowCreate,
    PromotionPolicyCreate,
    ReleaseReliabilityCreate,
    RolloutPropose,
)
from app.services.delivery import DeliveryService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)


def _idempotency_key(org_id: str, release_id: str, env_id: str, stage: str) -> str:
    raw = json.dumps({"org": org_id, "release": release_id, "env": env_id, "stage": stage}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


class ReleaseReliabilityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.reliability = RrReleaseRepo(session)
        self.verifications = RrVerificationRepo(session)
        self.health_gates = RrHealthGateRepo(session)
        self.rollouts = RrRolloutRepo(session)
        self.promotion_policies = RrPromotionPolicyRepo(session)
        self.promotion_requests = RrPromotionRequestRepo(session)
        self.freeze_windows = RrFreezeWindowRepo(session)
        self.rollbacks = RrRollbackRepo(session)
        self.releases = DeliveryReleaseRepository(session)
        self.environments = DeliveryEnvironmentRepository(session)
        self.deployments = DeliveryDeploymentRepository(session)
        self.artifacts = DeliveryArtifactRepository(session)
        self.delivery = DeliveryService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _get_row(self, organization_id: str, reliability_id: str) -> RrReleaseReliability:
        row = await self.reliability.get_by_id(reliability_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("ReleaseReliability", reliability_id)
        return row

    async def _env_tier(self, environment_id: str, organization_id: str) -> str:
        env = await self.environments.get_for_org(environment_id, organization_id)
        return env.tier if env else "STAGING"

    def _append_timeline(self, row: RrReleaseReliability, event: str, *, actor: str | None = None) -> None:
        timeline = list(row.timeline or [])
        timeline.append({"event": event, "at": datetime.now(UTC).isoformat(), "actor": actor})
        row.timeline = timeline

    # ---------------------------------------------------------- create/list
    async def create(
        self, user: User, org_context: OrgContext, payload: ReleaseReliabilityCreate,
    ) -> RrReleaseReliability:
        organization_id = self._ensure_write(user, org_context)
        release = await self.releases.get_by_id(payload.release_id)
        if not release or release.organization_id != organization_id:
            raise NotFoundError("Release", payload.release_id)
        env = await self.environments.get_for_org(payload.environment_id, organization_id)
        if not env:
            raise NotFoundError("Environment", payload.environment_id)
        key = _idempotency_key(organization_id, payload.release_id, payload.environment_id, "init")
        existing = await self.reliability.get_by_idempotency(organization_id, key)
        if existing:
            return existing
        mode = detect_provider_mode(payload.provider_type, configured=True)
        row = RrReleaseReliability(
            organization_id=organization_id,
            release_id=payload.release_id,
            deployment_id=payload.deployment_id,
            gitops_app_id=payload.gitops_app_id,
            environment_id=payload.environment_id,
            strategy=payload.strategy.upper(),
            baseline_version=payload.baseline_version or release.version,
            candidate_version=payload.candidate_version or release.version,
            artifact_digest=payload.artifact_digest,
            rollback_plan=payload.rollback_plan or release.rollback_plan,
            approval_required=env.requires_approval or env.tier == "PRODUCTION",
            provider_type=payload.provider_type,
            provider_mode=mode,
            idempotency_key=key,
            created_by=user.id,
            timeline=[{"event": "created", "at": datetime.now(UTC).isoformat(), "actor": user.id}],
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_reliability(
        self, user: User, org_context: OrgContext, *, offset: int = 0, limit: int = 50,
    ) -> tuple[list[RrReleaseReliability], int]:
        organization_id = self._ensure_read(user, org_context)
        return await self.reliability.list_for_org(organization_id, offset=offset, limit=limit)

    async def get_reliability(self, user: User, org_context: OrgContext, reliability_id: str) -> RrReleaseReliability:
        organization_id = self._ensure_read(user, org_context)
        return await self._get_row(organization_id, reliability_id)

    # --------------------------------------------------------- verification
    async def verify(self, user: User, org_context: OrgContext, reliability_id: str) -> dict:
        organization_id = self._ensure_write(user, org_context)
        row = await self._get_row(organization_id, reliability_id)
        tier = await self._env_tier(row.environment_id, organization_id)
        is_prod = tier == "PRODUCTION"
        start = time.perf_counter()

        await emit_event(
            self.session, DomainEventType.RELEASE_VERIFICATION_STARTED,
            organization_id=organization_id,
            payload={"reliability_id": row.id},
        )

        signals = await self._collect_signals(row, organization_id)
        vrun = RrVerificationRun(
            organization_id=organization_id,
            reliability_id=row.id,
            status="RUNNING",
            signals=signals,
            started_at=datetime.now(UTC),
        )
        self.session.add(vrun)
        await self.session.flush()

        gate = evaluate_health_gate(signals, environment_tier=tier, is_production=is_prod)
        hg = RrHealthGateResult(
            organization_id=organization_id,
            reliability_id=row.id,
            verification_run_id=vrun.id,
            decision=gate["decision"],
            signals=gate["signals"],
            thresholds=gate["thresholds"],
            evidence_refs=gate["evidence_refs"],
            evaluated_at=datetime.now(UTC),
        )
        self.session.add(hg)
        vrun.status = "COMPLETED"
        vrun.completed_at = datetime.now(UTC)
        row.verification_status = "PASSED" if gate["decision"] == "PASS" else gate["decision"]
        row.health_gate_status = gate["decision"]
        row.evidence_snapshot = {"gate": gate, "signals": signals}
        self._append_timeline(row, f"verification_{gate['decision']}", actor=user.id)

        await emit_event(
            self.session, DomainEventType.HEALTH_GATE_EVALUATED,
            organization_id=organization_id,
            payload={"reliability_id": row.id, "decision": gate["decision"]},
        )
        if gate["decision"] == "PASS":
            await emit_event(
                self.session, DomainEventType.RELEASE_VERIFICATION_PASSED,
                organization_id=organization_id, payload={"reliability_id": row.id},
            )
        elif gate["decision"] in ("FAIL", "INSUFFICIENT_EVIDENCE"):
            await emit_event(
                self.session, DomainEventType.RELEASE_VERIFICATION_FAILED,
                organization_id=organization_id,
                payload={"reliability_id": row.id, "decision": gate["decision"]},
            )
            rec = recommend_rollback(
                health_gate_decision=gate["decision"],
                environment_tier=tier,
            )
            if rec["create_incident"]:
                incident_id = f"rr-incident-{row.id[:8]}"
                rb = RrRollbackRecord(
                    organization_id=organization_id,
                    reliability_id=row.id,
                    kind=rec["kind"],
                    status=rec["status"],
                    automatic=False,
                    incident_id=incident_id,
                    verification={},
                    created_by=user.id,
                )
                self.session.add(rb)
                await emit_event(
                    self.session, DomainEventType.ROLLBACK_RECOMMENDED,
                    organization_id=organization_id,
                    payload={"reliability_id": row.id, "incident_id": incident_id},
                )

        try:
            from app.observability import metrics
            metrics.record_release_verification(gate["decision"], time.perf_counter() - start)
            metrics.record_health_gate(gate["decision"])
        except Exception:  # noqa: BLE001
            pass
        await self.session.flush()
        return {"verification_run_id": vrun.id, "gate": gate}

    async def _collect_signals(self, row: RrReleaseReliability, organization_id: str) -> dict:
        dep_health: dict = {}
        security_gate: str | None = None
        if row.deployment_id:
            dep = await self.deployments.get_by_id(row.deployment_id)
            if dep and dep.organization_id == organization_id:
                dep_health = {
                    "passed": (dep.health_validation or {}).get("passed", dep.status == "SUCCEEDED"),
                    "rollout_status": "Complete" if dep.status == "SUCCEEDED" else dep.status,
                    "restart_delta": (dep.health_validation or {}).get("restart_delta"),
                    "error_rate": (dep.health_validation or {}).get("error_rate"),
                    "latency_p99_ms": (dep.health_validation or {}).get("latency_p99_ms"),
                }
        try:
            from app.services.integration_readiness import IntegrationReadinessService
            obs_integrations = await IntegrationReadinessService(self.session).list_observability_for_org(
                organization_id,
            )
        except Exception:  # pragma: no cover
            obs_integrations = []
        return collect_observability_signals(
            obs_integrations,
            deployment_health=dep_health or None,
            security_gate=security_gate,
        )

    async def get_evidence(self, user: User, org_context: OrgContext, reliability_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        row = await self._get_row(organization_id, reliability_id)
        vruns = await self.verifications.list_for_reliability(row.id)
        gates = await self.health_gates.list_for_reliability(row.id)
        rollouts = await self.rollouts.list_for_reliability(row.id)
        rollbacks = await self.rollbacks.list_for_reliability(row.id)
        return {
            "verification_runs": [
                {"id": v.id, "status": v.status, "signals": v.signals, "started_at": str(v.started_at)}
                for v in vruns
            ],
            "health_gates": [
                {"id": g.id, "decision": g.decision, "signals": g.signals, "evaluated_at": str(g.evaluated_at)}
                for g in gates
            ],
            "rollout_operations": [
                {"id": r.id, "action": r.action, "status": r.status, "simulated": r.simulated}
                for r in rollouts
            ],
            "rollback_records": [
                {"id": rb.id, "kind": rb.kind, "status": rb.status, "automatic": rb.automatic}
                for rb in rollbacks
            ],
            "evidence_snapshot": row.evidence_snapshot,
        }

    # -------------------------------------------------------------- rollouts
    async def propose_rollout(
        self, user: User, org_context: OrgContext, reliability_id: str, payload: RolloutPropose,
    ) -> RrRolloutOperation:
        organization_id = self._ensure_write(user, org_context)
        row = await self._get_row(organization_id, reliability_id)
        tier = await self._env_tier(row.environment_id, organization_id)
        op = None
        if row.approval_required and tier == "PRODUCTION":
            op = await self.delivery.propose_operation(
                user, org_context,
                OperationCreate(
                    kind=DeliveryOperationKind.CANARY_SHIFT.value,
                    release_id=row.release_id,
                    environment_id=row.environment_id,
                    params={"reliability_id": row.id, "strategy": payload.strategy},
                ),
            )
        mode = row.provider_mode
        state = propose_rollout(
            provider_type=payload.provider_type,
            strategy=payload.strategy,
            target=payload.target or row.candidate_version or "app",
            steps=payload.traffic_steps,
            mode=mode,
        )
        rollout = RrRolloutOperation(
            organization_id=organization_id,
            reliability_id=row.id,
            operation_id=op.id if row.approval_required and tier == "PRODUCTION" else None,
            action="PROPOSE",
            status="PENDING" if rollout_needs_approval(row, tier) else "APPROVED",
            traffic_steps=state.get("traffic_steps", []),
            revision_history=[{"revision": state.get("revision")}],
            result=state,
            simulated=state.get("simulated", True),
            created_by=user.id,
        )
        row.rollout_state = state
        row.provider_type = payload.provider_type
        self._append_timeline(row, "rollout_proposed", actor=user.id)
        self.session.add(rollout)
        await emit_event(
            self.session, DomainEventType.ROLLOUT_PROPOSED,
            organization_id=organization_id, payload={"reliability_id": row.id},
        )
        await self.session.flush()
        return rollout

    async def _rollout_action(
        self, user: User, org_context: OrgContext, reliability_id: str, action: str,
    ) -> RrRolloutOperation:
        organization_id = self._ensure_write(user, org_context)
        row = await self._get_row(organization_id, reliability_id)
        tier = await self._env_tier(row.environment_id, organization_id)
        if row.approval_required and tier == "PRODUCTION":
            await self._ensure_rollout_approved(row, organization_id)
        state = row.rollout_state or {}
        explicit_simulation = bool((state or {}).get("explicit_simulation"))
        is_live = row.provider_mode == "live" and not explicit_simulation
        gate = LiveMutationGate(self.session)
        reg = await gate.ensure_registry(
            organization_id=organization_id,
            resource_type="release_reliability",
            resource_id=row.id,
            provider_type=(row.provider_type or "K8S").upper(),
            credential_id=None,
        )
        required = ["rollout.promote"] if action == "promote" else ["kubernetes.workloads.write"]
        if tier == "PRODUCTION":
            required.extend(["observability.metrics.query", "observability.logs.query"])
        preflight = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=reg.id,
            operation_type=f"release_rollout.{action}",
            resource_type="rr_rollout",
            resource_id=row.id,
            environment_id=row.environment_id,
            idempotency_key=make_idempotency_key(org_id=organization_id, operation=action, target_id=row.id),
            required_capabilities=required,
            approval_satisfied=True,
            explicit_simulation=explicit_simulation or row.provider_mode != "live",
        )
        if is_live and not preflight["allowed"]:
            raise NexoraException(
                preflight.get("reason") or "Rollout blocked by integration preflight",
                400,
                details={"integration_readiness": preflight.get("evidence_context")},
            )
        handlers = {
            "pause": pause_rollout, "resume": resume_rollout,
            "promote": lambda s: promote_rollout(s), "abort": abort_rollout,
        }
        fn = handlers.get(action)
        if not fn:
            raise NexoraException(f"Unknown rollout action: {action}", 400)
        new_state = fn(state)
        new_state["simulated"] = preflight.get("simulated", row.provider_mode != "live")
        new_state["integration_readiness"] = preflight.get("evidence_context")
        new_state["correlation_id"] = preflight.get("correlation_id")
        row.rollout_state = new_state
        rollout = RrRolloutOperation(
            organization_id=organization_id,
            reliability_id=row.id,
            action=action.upper(),
            status="SUCCEEDED",
            traffic_steps=new_state.get("traffic_steps", []),
            revision_history=new_state.get("revision_history", []),
            result=new_state,
            simulated=new_state.get("simulated", True),
            created_by=user.id,
        )
        if preflight.get("allowed"):
            await gate.record_execution(
                organization_id=organization_id, actor_id=user.id,
                connection_id=preflight.get("connection_id"),
                operation_type=f"release_rollout.{action}", resource_id=rollout.id,
                correlation_id=preflight["correlation_id"], outcome="succeeded", result_summary=new_state,
            )
        self.session.add(rollout)
        self._append_timeline(row, f"rollout_{action}", actor=user.id)
        event_map = {
            "promote": DomainEventType.ROLLOUT_PROMOTED,
            "pause": DomainEventType.ROLLOUT_PAUSED,
            "abort": DomainEventType.ROLLOUT_ABORTED,
        }
        if action in event_map:
            await emit_event(
                self.session, event_map[action],
                organization_id=organization_id, payload={"reliability_id": row.id},
            )
        try:
            from app.observability import metrics
            metrics.record_release_rollout(action)
        except Exception:  # noqa: BLE001
            pass
        await self.session.flush()
        return rollout

    async def pause_rollout(self, user, org_context, reliability_id):
        return await self._rollout_action(user, org_context, reliability_id, "pause")

    async def resume_rollout(self, user, org_context, reliability_id):
        return await self._rollout_action(user, org_context, reliability_id, "resume")

    async def promote_rollout(self, user, org_context, reliability_id):
        return await self._rollout_action(user, org_context, reliability_id, "promote")

    async def abort_rollout(self, user, org_context, reliability_id):
        return await self._rollout_action(user, org_context, reliability_id, "abort")

    async def rollback(
        self, user: User, org_context: OrgContext, reliability_id: str, *,
        target_revision: str | None = None,
    ) -> RrRollbackRecord:
        organization_id = self._ensure_write(user, org_context)
        row = await self._get_row(organization_id, reliability_id)
        tier = await self._env_tier(row.environment_id, organization_id)
        op = await self.delivery.propose_operation(
            user, org_context,
            OperationCreate(
                kind=DeliveryOperationKind.ROLLBACK.value,
                release_id=row.release_id,
                environment_id=row.environment_id,
                params={"reliability_id": row.id, "target_revision": target_revision},
            ),
        )
        if tier == "PRODUCTION":
            raise NexoraException(
                "Production rollback requires approval via /operations/{id}/decide then execute",
                400,
            )
        state = rollback_rollout(row.rollout_state or {}, target_revision=target_revision or row.baseline_version)
        row.rollout_state = state
        result = apply_rollback_result(success=True, target_revision=target_revision)
        record = RrRollbackRecord(
            organization_id=organization_id,
            reliability_id=row.id,
            operation_id=op.id,
            kind="MANUAL",
            status="SUCCEEDED",
            target_revision=target_revision or row.baseline_version,
            automatic=False,
            verification=result,
            created_by=user.id,
        )
        self.session.add(record)
        self._append_timeline(row, "rollback_executed", actor=user.id)
        await emit_event(
            self.session, DomainEventType.ROLLBACK_EXECUTED,
            organization_id=organization_id, payload={"reliability_id": row.id},
        )
        try:
            from app.observability import metrics
            metrics.record_release_rollback("succeeded")
        except Exception:  # noqa: BLE001
            pass
        await self.session.flush()
        return record

    async def get_history(self, user: User, org_context: OrgContext, reliability_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        row = await self._get_row(organization_id, reliability_id)
        rollouts = await self.rollouts.list_for_reliability(row.id)
        rollbacks = await self.rollbacks.list_for_reliability(row.id)
        return {
            "timeline": row.timeline,
            "rollout_state": inspect_rollout(row.rollout_state or {}),
            "rollout_operations": [
                {"action": r.action, "status": r.status, "simulated": r.simulated, "at": str(r.created_at)}
                for r in rollouts
            ],
            "rollback_records": [
                {"kind": rb.kind, "status": rb.status, "target_revision": rb.target_revision}
                for rb in rollbacks
            ],
        }

    async def _ensure_rollout_approved(self, row: RrReleaseReliability, organization_id: str) -> None:
        ops = await self.rollouts.list_for_reliability(row.id)
        pending = [o for o in ops if o.operation_id and o.status == "PENDING"]
        if pending:
            raise ForbiddenError("Rollout operation pending approval")

    # ----------------------------------------------------------- promotion
    async def ensure_promotion_policies(self, organization_id: str) -> list[RrPromotionPolicy]:
        existing = await self.promotion_policies.list_for_org(organization_id)
        if existing:
            return existing
        for pol in DEFAULT_POLICIES:
            self.session.add(RrPromotionPolicy(organization_id=organization_id, **pol))
        await self.session.flush()
        return await self.promotion_policies.list_for_org(organization_id)

    async def list_promotion_policies(self, user: User, org_context: OrgContext) -> list[RrPromotionPolicy]:
        organization_id = self._ensure_read(user, org_context)
        return await self.ensure_promotion_policies(organization_id)

    async def create_promotion_policy(
        self, user: User, org_context: OrgContext, payload: PromotionPolicyCreate,
    ) -> RrPromotionPolicy:
        organization_id = self._ensure_write(user, org_context)
        row = RrPromotionPolicy(organization_id=organization_id, **payload.model_dump())
        self.session.add(row)
        await self.session.flush()
        return row

    async def promotion_queue(self, user: User, org_context: OrgContext) -> list[RrPromotionRequest]:
        organization_id = self._ensure_read(user, org_context)
        return await self.promotion_requests.list_queue(organization_id)

    async def request_promotion(
        self, user: User, org_context: OrgContext, reliability_id: str,
        *, target_environment_id: str,
    ) -> RrPromotionRequest:
        organization_id = self._ensure_write(user, org_context)
        row = await self._get_row(organization_id, reliability_id)
        source_env = await self.environments.get_for_org(row.environment_id, organization_id)
        target_env = await self.environments.get_for_org(target_environment_id, organization_id)
        if not source_env or not target_env:
            raise NotFoundError("Environment", target_environment_id)
        policy = await self.promotion_policies.get_policy(
            organization_id, source_env.tier, target_env.tier,
        )
        if not policy:
            await self.ensure_promotion_policies(organization_id)
            policy = await self.promotion_policies.get_policy(
                organization_id, source_env.tier, target_env.tier,
            )
        freezes = await self.freeze_windows.list_for_org(organization_id)
        freeze_dicts = [
            {"active": f.active, "environment_tier": f.environment_tier,
             "starts_at": f.starts_at, "ends_at": f.ends_at}
            for f in freezes
        ]
        frozen = is_freeze_active(freeze_dicts, tier=target_env.tier)
        gate = await self.health_gates.latest_for_reliability(row.id)
        eval_result = evaluate_promotion(
            source_verification=row.verification_status,
            security_gate=gate.decision if gate else None,
            artifact_digest=row.artifact_digest or "",
            existing_digest=row.artifact_digest,
            policy={
                "requires_verification": policy.requires_verification if policy else True,
                "requires_security_gate": policy.requires_security_gate if policy else True,
                "requires_approval": policy.requires_approval if policy else True,
                "digest_immutable": policy.digest_immutable if policy else True,
            },
            freeze_active=frozen,
            environment_tier=target_env.tier,
        )
        status = "BLOCKED" if not eval_result["allowed"] else "PENDING"
        req = RrPromotionRequest(
            organization_id=organization_id,
            reliability_id=row.id,
            source_environment_id=row.environment_id,
            target_environment_id=target_environment_id,
            status=status,
            block_reason="; ".join(eval_result["block_reasons"]) if eval_result["block_reasons"] else None,
            artifact_digest=row.artifact_digest,
            created_by=user.id,
        )
        self.session.add(req)
        event = DomainEventType.PROMOTION_BLOCKED if status == "BLOCKED" else DomainEventType.PROMOTION_REQUESTED
        await emit_event(
            self.session, event,
            organization_id=organization_id,
            payload={"reliability_id": row.id, "target_tier": target_env.tier},
        )
        try:
            from app.observability import metrics
            metrics.record_release_promotion(status)
        except Exception:  # noqa: BLE001
            pass
        await self.session.flush()
        return req

    # --------------------------------------------------------- freeze windows
    async def list_freeze_windows(self, user: User, org_context: OrgContext) -> list[RrFreezeWindow]:
        organization_id = self._ensure_read(user, org_context)
        return await self.freeze_windows.list_for_org(organization_id)

    async def create_freeze_window(
        self, user: User, org_context: OrgContext, payload: FreezeWindowCreate,
    ) -> RrFreezeWindow:
        organization_id = self._ensure_write(user, org_context)
        row = RrFreezeWindow(
            organization_id=organization_id,
            name=payload.name,
            environment_tier=payload.environment_tier,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            created_by=user.id,
        )
        self.session.add(row)
        await emit_event(
            self.session, DomainEventType.FREEZE_WINDOW_STARTED,
            organization_id=organization_id, payload={"freeze_id": row.id, "name": row.name},
        )
        await self.session.flush()
        return row

    # -------------------------------------------------------------- analytics
    async def release_analytics(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        rows, _ = await self.reliability.list_for_org(organization_id, limit=500)
        rollbacks = await self.rollbacks.list_for_org(organization_id)
        promotions = await self.promotion_requests.list_queue(organization_id)
        gates = []
        for r in rows[:50]:
            g = await self.health_gates.latest_for_reliability(r.id)
            if g:
                gates.append({"decision": g.decision})
        analytics = compute_release_analytics(
            reliabilities=[{"verification_status": r.verification_status, "provider_mode": r.provider_mode} for r in rows],
            rollbacks=[{"status": rb.status} for rb in rollbacks],
            promotions=[{"status": p.status} for p in promotions],
            verifications=gates,
        )
        try:
            from app.observability import metrics
            metrics.set_release_change_failure_rate(analytics["change_failure_rate"])
        except Exception:  # noqa: BLE001
            pass
        return analytics


def rollout_needs_approval(row: RrReleaseReliability, tier: str) -> bool:
    return row.approval_required and tier == "PRODUCTION"
