"""Pilot execution orchestration (Sprint 66B)."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError, NexoraException, NotFoundError, ValidationError
from app.integration_readiness.live_gate import CONTROL_PLANE_CAPABILITIES, LiveMutationGate
from app.integration_readiness.preflight import make_idempotency_key
from app.models.delivery import DeliveryEnvironment
from app.models.pilot import (
    PILOT_ALLOWED_ACTIONS,
    PilotApproval,
    PilotEnrollment,
    PilotLiveOperation,
    PilotStage,
)
from app.models.user import User
from app.observability.metrics import (
    record_pilot_approval_event,
    record_pilot_stage_duration,
    record_pilot_verification,
)
from app.models.customer_pilot import PilotApprovalPackage
from app.pilot.approval_package import build_approval_package, approval_package_html, approval_package_markdown, verification_checklist_markdown
from app.pilot.customer_portal import rollback_plan_hash
from app.pilot.evidence_pack import build_evidence_pack, evidence_pack_html, evidence_pack_markdown
from app.pilot.operations import PILOT_MUTATION_ACTIONS, PILOT_OPERATION_CATALOG
from app.pilot.stages import PILOT_EXECUTION_STAGES, PILOT_STAGE_KEYS, next_stage_key, stage_index
from app.pilot.verification import (
    collect_before_state,
    evaluate_scale_verification,
    evaluate_verification,
    merge_after_state,
)
from app.platform.events import DomainEventType, emit_event
from app.repositories.pilot import PilotApprovalRepo, PilotLiveOperationRepo, PilotStageRepo
from app.schemas.pilot import (
    ConfirmationTokenView,
    LiveOperationView,
    OperationTemplateView,
    PilotApprovalCreate,
    PilotApprovalDecisionView,
    PilotApprovalView,
    PilotDashboardView,
    PilotEvidencePackView,
    PilotExecutionStatusView,
    PilotStageView,
)
from app.tenancy.permissions import can_read_resources, can_write_resources


def _payload_hash(action: str, resource_name: str, environment_id: str, params: dict) -> str:
    blob = json.dumps(
        {"action": action, "resource_name": resource_name, "environment_id": environment_id, "params": params},
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


class PilotExecutionMixin:
    """Execution-stage workflow mixed into PilotService."""

    stages: PilotStageRepo
    approvals: PilotApprovalRepo
    live_ops: PilotLiveOperationRepo

    session: AsyncSession

    def _approval_expiry_hours(self) -> int:
        return int(getattr(settings, "PILOT_APPROVAL_EXPIRY_HOURS", 24))

    async def _seed_execution_stages(self, enrollment: PilotEnrollment) -> list[PilotStage]:
        existing = {s.stage_key: s for s in await self.stages.list_for_enrollment(enrollment.id)}
        rows: list[PilotStage] = []
        for spec in PILOT_EXECUTION_STAGES:
            if spec["key"] in existing:
                rows.append(existing[spec["key"]])
                continue
            row = PilotStage(
                organization_id=enrollment.organization_id,
                enrollment_id=enrollment.id,
                stage_key=spec["key"],
                title=spec["title"],
                status="PENDING",
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return sorted(rows, key=lambda s: stage_index(s.stage_key))

    async def _ensure_execution_started(self, enrollment: PilotEnrollment) -> None:
        if enrollment.execution_status == "NOT_STARTED":
            enrollment.execution_status = "IN_PROGRESS"
            enrollment.current_stage = PILOT_STAGE_KEYS[0]
            await self._seed_execution_stages(enrollment)

    def _assert_prior_stages_complete(self, stages: list[PilotStage], stage_key: str) -> None:
        idx = stage_index(stage_key)
        for s in stages:
            if stage_index(s.stage_key) < idx and s.status != "COMPLETED":
                raise ValidationError(
                    f"Stage {stage_key} cannot start until {s.stage_key} is completed",
                )

    async def _complete_stage(
        self,
        enrollment: PilotEnrollment,
        stage_key: str,
        *,
        owner_id: str | None = None,
        evidence: dict | None = None,
        blockers: list | None = None,
        rollback_plan: str | None = None,
        outcome: str | None = None,
        failed: bool = False,
    ) -> PilotStage:
        await self._ensure_execution_started(enrollment)
        stages = await self._seed_execution_stages(enrollment)
        self._assert_prior_stages_complete(stages, stage_key)
        stage = next(s for s in stages if s.stage_key == stage_key)
        if stage.status == "COMPLETED":
            return stage
        now = datetime.now(UTC)
        if not stage.started_at:
            stage.started_at = now
        stage.owner_id = owner_id or stage.owner_id
        stage.evidence = evidence or stage.evidence or {}
        stage.blockers = blockers or []
        stage.rollback_plan = rollback_plan or stage.rollback_plan
        stage.outcome = outcome
        stage.status = "FAILED" if failed else "COMPLETED"
        stage.completed_at = now
        enrollment.current_stage = next_stage_key(stage_key) or stage_key
        if failed:
            enrollment.execution_status = "FAILED"
        elif stage_key == "COMPLETE":
            enrollment.execution_status = "COMPLETED"
            enrollment.completed_at = now
            await emit_event(
                self.session, DomainEventType.PILOT_COMPLETED,
                organization_id=enrollment.organization_id,
                payload={"enrollment_id": enrollment.id},
            )
        if stage.started_at and stage.completed_at:
            started = stage.started_at if stage.started_at.tzinfo else stage.started_at.replace(tzinfo=UTC)
            completed = stage.completed_at if stage.completed_at.tzinfo else stage.completed_at.replace(tzinfo=UTC)
            record_pilot_stage_duration(stage_key, (completed - started).total_seconds())
        await self.session.flush()
        return stage

    async def _maybe_complete_stage(
        self,
        enrollment: PilotEnrollment,
        stage_key: str,
        **kwargs,
    ) -> PilotStage | None:
        try:
            return await self._complete_stage(enrollment, stage_key, **kwargs)
        except ValidationError:
            return None

    async def _complete_stage_required(
        self,
        enrollment: PilotEnrollment,
        stage_key: str,
        **kwargs,
    ) -> PilotStage:
        """Complete a stage or raise — used when stage advancement is mandatory."""
        return await self._complete_stage(enrollment, stage_key, **kwargs)

    def _check_safety_controls(self, enrollment: PilotEnrollment, *, mutation: bool) -> None:
        if enrollment.kill_switch:
            raise ValidationError("Pilot kill switch is active — all operations are blocked")
        if mutation and enrollment.operation_count >= enrollment.operation_limit:
            raise ValidationError("Pilot operation limit reached for this enrollment")
        if mutation and enrollment.last_mutation_at:
            last = enrollment.last_mutation_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            cooldown = timedelta(minutes=enrollment.cooldown_minutes or 30)
            if datetime.now(UTC) - last < cooldown:
                raise ValidationError("Mutation cooldown active — wait before next live operation")

    async def advance_stage(
        self,
        user: User,
        org_context: OrgContext,
        stage_key: str,
        *,
        evidence: dict | None = None,
        blockers: list | None = None,
        rollback_plan: str | None = None,
        outcome: str | None = None,
    ) -> PilotStageView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        stage = await self._complete_stage(
            enrollment, stage_key, owner_id=user.id,
            evidence=evidence, blockers=blockers,
            rollback_plan=rollback_plan, outcome=outcome,
        )
        return PilotStageView.model_validate(stage)

    async def get_execution_status(self, user: User, org_context: OrgContext) -> PilotExecutionStatusView:
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        await self.session.refresh(enrollment)
        stages = await self._seed_execution_stages(enrollment)
        await self.session.flush()
        return PilotExecutionStatusView(
            enrollment_id=enrollment.id,
            execution_status=enrollment.execution_status,
            current_stage=enrollment.current_stage,
            kill_switch=enrollment.kill_switch,
            operation_count=enrollment.operation_count,
            operation_limit=enrollment.operation_limit,
            cooldown_minutes=enrollment.cooldown_minutes,
            stages=[PilotStageView.model_validate(s) for s in stages],
        )

    async def list_operation_catalog(self, user: User, org_context: OrgContext) -> list[OperationTemplateView]:
        self._ensure_read(user, org_context)
        return [OperationTemplateView(**t) for t in PILOT_OPERATION_CATALOG.values()]

    async def set_kill_switch(self, user: User, org_context: OrgContext, *, enabled: bool) -> dict:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        enrollment.kill_switch = enabled
        if enabled:
            enrollment.execution_status = "BLOCKED"
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id, payload={"reason": "kill_switch"},
            )
        elif enrollment.execution_status == "BLOCKED":
            enrollment.execution_status = "IN_PROGRESS"
        await self.session.flush()
        return {"kill_switch": enabled, "execution_status": enrollment.execution_status}

    async def create_customer_approval(
        self, user: User, org_context: OrgContext, payload: PilotApprovalCreate,
    ) -> PilotApprovalView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        op = await self.live_ops.get_for_org(payload.operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", payload.operation_id)
        if op.status not in ("PENDING_CONFIRMATION", "AWAITING_APPROVAL"):
            raise ValidationError("Operation is not awaiting customer approval")
        phash = _payload_hash(op.action, op.resource_name, op.environment_id or "", op.params or {})
        if op.payload_hash and op.payload_hash != phash:
            raise ValidationError("Operation payload changed — re-propose before approval")
        op.payload_hash = phash
        env = await self.session.get(DeliveryEnvironment, op.environment_id)
        env_name = env.name if env else op.environment_id or "unknown"
        if env and (env.tier or "").upper() == "PRODUCTION":
            raise ValidationError("Production environments are excluded from pilot approvals")
        expires = datetime.now(UTC) + timedelta(hours=self._approval_expiry_hours())
        approval_status = "APPROVED" if payload.approve else "PENDING"
        approval = PilotApproval(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            operation_id=op.id,
            approver_name=payload.approver_name,
            approver_email=payload.approver_email,
            operation_summary=payload.operation_summary,
            target_environment=env_name,
            rollback_plan=payload.rollback_plan,
            payload_hash=phash,
            status=approval_status,
            expires_at=expires,
            approved_at=datetime.now(UTC) if payload.approve else None,
        )
        self.session.add(approval)
        await self.session.flush()
        op.approval_id = approval.id
        op.rollback_plan = payload.rollback_plan
        if payload.approve:
            op.status = "PENDING_CONFIRMATION"
            await self._complete_stage_required(
                enrollment, "CUSTOMER_APPROVAL", owner_id=user.id,
                evidence={"approval_id": approval.id, "approver": payload.approver_email},
                outcome="Customer approval recorded",
            )
            record_pilot_approval_event("approved")
        else:
            op.status = "AWAITING_APPROVAL"
            record_pilot_approval_event("pending")
        await self.session.flush()
        await self._snapshot_approval_package(
            organization_id, enrollment, op, approval, env_name,
        )
        return PilotApprovalView.model_validate(approval)

    _DEFAULT_APPROVAL_RATIONALE = (
        "Internal pilot approval for controlled non-production execution-readiness validation. "
        "Execution remains separately gated by typed confirmation."
    )

    async def get_customer_approval(
        self, user: User, org_context: OrgContext, approval_id: str,
    ) -> PilotApprovalView:
        organization_id = self._ensure_read(user, org_context)
        approval = await self.approvals.get_for_org(approval_id, organization_id)
        if not approval:
            raise NotFoundError("PilotApproval", approval_id)
        return PilotApprovalView.model_validate(approval)

    async def decide_customer_approval(
        self,
        user: User,
        org_context: OrgContext,
        approval_id: str,
        *,
        approve: bool = True,
        rationale: str | None = None,
    ) -> PilotApprovalDecisionView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        approval = await self.approvals.get_for_org(approval_id, organization_id)
        if not approval:
            raise NotFoundError("PilotApproval", approval_id)
        if approval.status != "PENDING":
            raise ValidationError(f"Approval is not pending (status={approval.status})")

        expires = approval.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if datetime.now(UTC) > expires:
            approval.status = "EXPIRED"
            record_pilot_approval_event("expired")
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id,
                payload={"reason": "approval_expired", "approval_id": approval.id},
            )
            await self.session.flush()
            raise ValidationError("Customer approval has expired")

        op = await self.live_ops.get_for_org(approval.operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", approval.operation_id)
        if op.approval_id != approval.id:
            raise ValidationError("Approval is not linked to the current operation")
        if op.status not in ("AWAITING_APPROVAL", "PENDING_CONFIRMATION"):
            raise ValidationError("Operation is not awaiting approval decision")

        phash = _payload_hash(op.action, op.resource_name, op.environment_id or "", op.params or {})
        if approval.payload_hash != phash:
            approval.status = "INVALIDATED"
            record_pilot_approval_event("invalidated")
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id,
                payload={"reason": "approval_payload_mismatch", "approval_id": approval.id},
            )
            await self.session.flush()
            raise ValidationError("Approval payload hash mismatch with current operation")

        decision_rationale = rationale or self._DEFAULT_APPROVAL_RATIONALE

        if not approve:
            approval.status = "REJECTED"
            op.status = "CANCELLED"
            record_pilot_approval_event("rejected")
            await self.audit.log(
                action="pilot.approval_decided",
                resource_type="pilot_approval",
                resource_id=approval.id,
                user_id=user.id,
                organization_id=organization_id,
                details={
                    "operation_id": op.id,
                    "approve": False,
                    "approver_name": approval.approver_name,
                    "approver_email": approval.approver_email,
                    "payload_hash": approval.payload_hash,
                    "decision_rationale": decision_rationale,
                },
            )
            await self.session.flush()
            base = PilotApprovalView.model_validate(approval)
            return PilotApprovalDecisionView(
                **base.model_dump(),
                decision_rationale=decision_rationale,
            )

        approval.status = "APPROVED"
        approval.approved_at = datetime.now(UTC)
        await self._check_approval_integration_readiness(op, approval, organization_id)
        op.status = "PENDING_CONFIRMATION"
        await self._complete_stage_required(
            enrollment, "CUSTOMER_APPROVAL", owner_id=user.id,
            evidence={
                "approval_id": approval.id,
                "approver": approval.approver_email,
                "decision_rationale": decision_rationale,
            },
            outcome="Customer approval recorded",
        )
        record_pilot_approval_event("approved")
        await self.audit.log(
            action="pilot.approval_decided",
            resource_type="pilot_approval",
            resource_id=approval.id,
            user_id=user.id,
            organization_id=organization_id,
            details={
                "operation_id": op.id,
                "approve": True,
                "approver_name": approval.approver_name,
                "approver_email": approval.approver_email,
                "payload_hash": approval.payload_hash,
                "decision_rationale": decision_rationale,
            },
        )
        await self.session.flush()
        base = PilotApprovalView.model_validate(approval)
        return PilotApprovalDecisionView(
            **base.model_dump(),
            decision_rationale=decision_rationale,
        )

    async def _validate_approval(self, op: PilotLiveOperation, organization_id: str) -> PilotApproval:
        if not op.approval_id:
            raise ValidationError("Customer approval required before execution")
        approval = await self.approvals.get_for_org(op.approval_id, organization_id)
        if not approval:
            raise NotFoundError("PilotApproval", op.approval_id or "")
        phash = _payload_hash(op.action, op.resource_name, op.environment_id or "", op.params or {})
        if approval.payload_hash != phash or (op.payload_hash and op.payload_hash != phash):
            approval.status = "INVALIDATED"
            record_pilot_approval_event("invalidated")
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id,
                payload={"reason": "approval_payload_mismatch", "approval_id": approval.id},
            )
            raise ValidationError("Approval invalidated — operation payload changed")
        if approval.status == "EXPIRED" or datetime.now(UTC) > (
            approval.expires_at if approval.expires_at.tzinfo else approval.expires_at.replace(tzinfo=UTC)
        ):
            approval.status = "EXPIRED"
            record_pilot_approval_event("expired")
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id,
                payload={"reason": "approval_expired", "approval_id": approval.id},
            )
            raise ValidationError("Customer approval has expired")
        if approval.status != "APPROVED":
            raise ValidationError(f"Approval status is {approval.status}")
        await self._check_approval_integration_readiness(op, approval, organization_id)
        return approval

    async def issue_confirmation_token(
        self, user: User, org_context: OrgContext, operation_id: str,
    ) -> ConfirmationTokenView:
        """Issue a fresh confirmation token for a pending operation (operator recovery)."""
        organization_id = self._ensure_write(user, org_context)
        op = await self.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        if op.status != "PENDING_CONFIRMATION":
            raise ValidationError("Confirmation token can only be issued for pending operations")
        token = secrets.token_urlsafe(32)
        op.confirmation_token = hashlib.sha256(token.encode()).hexdigest()[:64]
        await self.audit.log(
            action="pilot.confirmation_token_issued",
            resource_type="pilot_live_operation",
            resource_id=op.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"operation_id": op.id, "action": op.action},
        )
        await self.session.flush()
        return ConfirmationTokenView(operation_id=op.id, confirmation_token=token)

    async def verify_live_operation(
        self,
        user: User,
        org_context: OrgContext,
        operation_id: str,
        *,
        kubernetes_evidence: dict | None = None,
        prometheus_evidence: dict | None = None,
        events_evidence: dict | None = None,
        advance_complete: bool = True,
        attempt_rollback: bool = True,
    ) -> LiveOperationView:
        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        op = await self.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        if op.status not in ("PENDING_VERIFICATION", "SUCCEEDED", "FAILED"):
            raise ValidationError("Operation is not ready for verification")
        source_mode = (op.source_mode or "UNAVAILABLE").upper()
        template = PILOT_OPERATION_CATALOG.get(op.template_id or "")
        target_replicas = (op.params or {}).get("replicas")
        if (
            op.action == "scale_deployment"
            and target_replicas is not None
            and (kubernetes_evidence or prometheus_evidence)
        ):
            verdict = evaluate_scale_verification(
                before=op.before_state or {},
                execution_result=op.result or {},
                kubernetes_evidence=kubernetes_evidence,
                prometheus_evidence=prometheus_evidence,
                target_replicas=int(target_replicas),
                source_mode=source_mode,
                events_evidence=events_evidence,
            )
        else:
            after = merge_after_state(op.result or {}, op.after_state)
            verdict = evaluate_verification(
                before=op.before_state or {},
                after=after,
                execution_result=op.result or {},
                source_mode=source_mode,
            )
        from app.pilot.verification import is_rollback_eligible

        rollback_result: dict | None = None
        if (
            attempt_rollback
            and is_rollback_eligible(verdict)
            and template.get("reversible")
            and op.action == "scale_deployment"
            and not (op.result or {}).get("simulated")
        ):
            rollback_result = await self._attempt_pilot_rollback(
                user, org_context, op,
                failed_rules=verdict.get("failed_verification_rules") or [],
                evidence=verdict.get("after") or {},
            )
            if rollback_result:
                verdict["rollback"] = rollback_result
        op.verification = verdict
        op.after_state = verdict.get("after") or op.after_state
        op.verification_status = verdict["verification_status"]
        if verdict["verification_status"] == "VERIFIED":
            op.status = "SUCCEEDED"
            record_pilot_verification("verified")
            await self._maybe_complete_stage(
                enrollment, "VERIFY", owner_id=user.id,
                evidence=verdict,
                outcome=verdict["verification_status"],
            )
        elif verdict["verification_status"] == "VERIFICATION_FAILED":
            op.status = "FAILED"
            enrollment.execution_status = "FAILED"
            record_pilot_verification("failed")
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id,
                payload={"reason": "verification_failed", "operation_id": op.id},
            )
            await self._maybe_complete_stage(
                enrollment, "VERIFY", owner_id=user.id,
                evidence=verdict,
                outcome=verdict["verification_status"],
                failed=True,
            )
        else:
            record_pilot_verification("insufficient")
        if verdict["verification_status"] == "VERIFIED" and advance_complete:
            await self._maybe_complete_stage(
                enrollment, "COMPLETE", owner_id=user.id,
                evidence={"operation_id": op.id},
                outcome="Pilot execution completed with verified operation",
            )
        await self.session.flush()
        return LiveOperationView(
            id=op.id, action=op.action, resource_name=op.resource_name,
            status=op.status, preflight=op.preflight or {}, result=op.result or {},
            verification=op.verification or {}, correlation_id=op.correlation_id,
            source_mode=op.source_mode, verification_status=op.verification_status,
        )

    async def _attempt_pilot_rollback(
        self,
        user: User,
        org_context: OrgContext,
        op: PilotLiveOperation,
        *,
        failed_rules: list[str] | None = None,
        evidence: dict | None = None,
    ) -> dict | None:
        from app.control_plane.kubernetes import operations as k8s_ops
        from app.models.integration_readiness import IntConnectionRegistry

        organization_id = org_context.requires_organization
        params = dict(op.params or {})
        rollback_replicas = params.get("from_replicas", 1)
        registry_id = op.cluster_id
        row = await self.session.get(IntConnectionRegistry, registry_id)
        if row is None:
            for candidate in await self.readiness.registry.list_for_org(organization_id):
                if candidate.provider_type == "KUBERNETES":
                    row = candidate
                    break
        if row is None:
            return {"attempted": False, "reason": "integration_not_found"}
        secret = await self.readiness._resolve_secret(row, user, org_context)
        if not secret:
            return {"attempted": False, "reason": "credential_unavailable"}
        write_params = {
            "namespace": params.get("namespace", "default"),
            "name": op.resource_name,
            "replicas": int(rollback_replicas),
        }
        result = await k8s_ops.execute_write(
            secret, "scale_deployment", write_params, explicit_simulation=False,
        )
        await self.audit.log(
            action="pilot.live_operation_rollback",
            resource_type="pilot_live_operation",
            resource_id=op.id,
            user_id=user.id,
            organization_id=organization_id,
            details={
                "rollback_replicas": rollback_replicas,
                "result": result,
                "failed_verification_rules": failed_rules or [],
                "supporting_evidence": evidence or {},
            },
        )
        return {
            "attempted": True,
            "rollback_replicas": rollback_replicas,
            "result": result,
            "failed_verification_rules": failed_rules or [],
            "supporting_evidence": evidence or {},
        }

    async def export_evidence_pack(self, user: User, org_context: OrgContext) -> PilotEvidencePackView:
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        readiness = await self.get_readiness(user, org_context)
        assessment = await self.get_assessment(user, org_context)
        scorecard = await self.get_scorecard(user, org_context)
        baseline = self._current_baseline_doc(enrollment.baseline)
        stages = await self._seed_execution_stages(enrollment)
        ops = list((await self.session.execute(
            select(PilotLiveOperation).where(
                PilotLiveOperation.organization_id == organization_id,
            ).order_by(PilotLiveOperation.created_at.desc()).limit(5)
        )).scalars().all())
        latest_op = ops[0] if ops else None
        approval = None
        if latest_op and latest_op.approval_id:
            approval = await self.approvals.get_for_org(latest_op.approval_id, organization_id)
        pack = build_evidence_pack({
            "enrollment": {
                "id": enrollment.id,
                "execution_status": enrollment.execution_status,
                "kill_switch": enrollment.kill_switch,
            },
            "readiness": readiness.model_dump(),
            "assessment": assessment.model_dump() if assessment else None,
            "scorecard": scorecard.model_dump(),
            "baseline": {
                "current": baseline,
                "history": (enrollment.baseline or {}).get("history", []) if enrollment.baseline else [],
            },
            "stages": [PilotStageView.model_validate(s).model_dump() for s in stages],
            "operation": {
                "id": latest_op.id,
                "action": latest_op.action,
                "status": latest_op.status,
                "source_mode": latest_op.source_mode,
                "verification_status": latest_op.verification_status,
                "before_state": latest_op.before_state,
                "after_state": latest_op.after_state,
                "correlation_id": latest_op.correlation_id,
            } if latest_op else None,
            "approval": PilotApprovalView.model_validate(approval).model_dump() if approval else None,
            "blockers": [b for s in stages for b in (s.blockers or [])],
            "recommendations": assessment.recommendations if assessment else [],
        })
        await emit_event(
            self.session, DomainEventType.PILOT_SUPPORT_BUNDLE_GENERATED,
            organization_id=organization_id, payload={"type": "evidence_pack"},
        )
        return PilotEvidencePackView(
            json_pack=pack,
            markdown=evidence_pack_markdown(pack),
            html=evidence_pack_html(pack),
        )

    async def get_pilot_dashboard(self, user: User, org_context: OrgContext) -> PilotDashboardView:
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        readiness = await self.get_readiness(user, org_context)
        stages = await self._seed_execution_stages(enrollment)
        blocked = sum(1 for s in stages if s.status == "BLOCKED")
        completed = sum(1 for s in stages if s.status == "COMPLETED")
        ops = list((await self.session.execute(
            select(PilotLiveOperation).where(PilotLiveOperation.organization_id == organization_id)
        )).scalars().all())
        verified = sum(1 for o in ops if o.verification_status == "VERIFIED")
        failed_v = sum(1 for o in ops if o.verification_status == "VERIFICATION_FAILED")
        approved = sum(1 for o in ops if o.approval_id)
        conns = await self.readiness.list_connections(user, org_context)
        return PilotDashboardView(
            readiness_score=readiness.readiness_score,
            execution_status=enrollment.execution_status,
            integration_states=[{"provider": c.provider_type, "state": c.lifecycle_state, "mode": c.provider_mode} for c in conns],
            stages_completed=completed,
            stages_blocked=blocked,
            approved_operations=approved,
            verified_operations=verified,
            failed_verifications=failed_v,
            time_to_first_value_seconds=None,
        )

    def _resolve_source_mode(self, preflight: dict) -> str:
        if preflight.get("simulated"):
            return "SIMULATED"
        if preflight.get("offline"):
            return "OFFLINE"
        if preflight.get("connection_id"):
            return "LIVE"
        return "UNAVAILABLE"

    async def _propose_with_safety(
        self,
        enrollment: PilotEnrollment,
        user: User,
        organization_id: str,
        *,
        action: str,
        template_id: str | None,
        resource_name: str,
        environment_id: str,
        cluster_id: str | None,
        params: dict | None,
        rollback_plan: str | None,
        namespace: str | None = None,
        idempotency_key: str | None = None,
    ) -> PilotLiveOperation:
        mutation = action in PILOT_MUTATION_ACTIONS
        self._check_safety_controls(enrollment, mutation=mutation)
        await self._ensure_execution_started(enrollment)
        await self._assert_stages_completed(
            enrollment, "CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT", "BASELINE_CAPTURE",
        )
        env = await self.session.get(DeliveryEnvironment, environment_id)
        if not env or env.organization_id != organization_id:
            raise NotFoundError("Environment", environment_id)
        if (env.tier or "").upper() == "PRODUCTION":
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id,
                payload={"reason": "production_environment", "action": action},
            )
            raise ValidationError("Production environments are excluded from pilot live operations")
        merged_params = dict(params or {})
        if namespace:
            merged_params.setdefault("namespace", namespace)
        token = secrets.token_urlsafe(32)
        phash = _payload_hash(action, resource_name, environment_id, merged_params)
        before = collect_before_state(
            resource_name=resource_name,
            environment_tier=env.tier or "NON_PRODUCTION",
            params=merged_params,
        )
        correlation_id = idempotency_key or make_idempotency_key(
            org_id=organization_id, operation=action, target_id=resource_name,
        )
        op = PilotLiveOperation(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            action=action,
            template_id=template_id,
            resource_name=resource_name,
            environment_id=environment_id,
            cluster_id=cluster_id,
            params=merged_params,
            payload_hash=phash,
            rollback_plan=rollback_plan,
            before_state=before,
            status="PENDING_CONFIRMATION",
            confirmation_token=hashlib.sha256(token.encode()).hexdigest()[:64],
            created_by=user.id,
            correlation_id=correlation_id,
            preflight={},
        )
        self.session.add(op)
        await self.session.flush()

        gate = LiveMutationGate(self.session)
        template = PILOT_OPERATION_CATALOG.get(template_id or "")
        required = template.get("required_capabilities") if template else CONTROL_PLANE_CAPABILITIES.get(
            action, ["kubernetes.workloads.write"],
        )
        registry_id = cluster_id or getattr(settings, "PILOT_INTERNAL_K8S_REGISTRY_ID", None)
        resolved = await gate._resolve_registry(
            organization_id,
            integration_connection_id=registry_id,
            credential_id=None,
            resource_lookup=("marketplace", cluster_id) if cluster_id else None,
        )
        if resolved is None:
            for row in await gate.registry.list_for_org(organization_id):
                if row.provider_type == "KUBERNETES" and row.lifecycle_state in ("CONNECTED", "DEGRADED"):
                    resolved = row
                    break
        integration_id = resolved.id if resolved else registry_id
        ns = merged_params.get("namespace", "default")
        preflight_result = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=integration_id,
            operation_type=action,
            resource_type="kubernetes_deployment",
            resource_id=f"{ns}/{resource_name}",
            environment_id=environment_id,
            idempotency_key=correlation_id,
            required_capabilities=required,
            approval_satisfied=False,
            explicit_simulation=False,
        )
        reason_code = preflight_result.get("reason_code")
        if not preflight_result.get("allowed") and reason_code not in ("APPROVAL_REQUIRED", None):
            raise ValidationError(preflight_result.get("reason") or "Preflight blocked for proposal")
        live_eligible = (
            preflight_result.get("allowed")
            or reason_code == "APPROVAL_REQUIRED"
            or "approval" in (preflight_result.get("reason") or "").lower()
        )
        op.preflight = {
            **preflight_result,
            "execution_label": "LIVE-ELIGIBLE / NOT EXECUTED",
            "live_eligible": live_eligible,
            "proposal_phase": True,
            "resource_name": resource_name,
            "resource_id": f"{ns}/{resource_name}",
            "environment_id": environment_id,
            "namespace": ns,
            "action": action,
        }
        op.source_mode = "LIVE" if live_eligible and not preflight_result.get("simulated") else self._resolve_source_mode(preflight_result)
        await self._complete_stage_required(
            enrollment, "PROPOSE_OPERATION", owner_id=user.id,
            evidence={
                "operation_id": op.id,
                "action": action,
                "template_id": template_id,
                "preflight_reason_code": reason_code,
                "execution_label": op.preflight.get("execution_label"),
                "resource_name": resource_name,
            },
            rollback_plan=rollback_plan,
            outcome=f"Proposed {action} on {resource_name}",
        )
        op._confirmation_token_plain = token  # type: ignore[attr-defined]
        return op

    async def close_internal_pilot(
        self,
        user: User,
        org_context: OrgContext,
        *,
        kubernetes_evidence: dict | None = None,
        prometheus_evidence: dict | None = None,
        events_evidence: dict | None = None,
        integration_evidence: dict | None = None,
    ) -> dict:
        """Read-only closure gate — advances COMPLETE only when evidence is fully verified."""
        from app.pilot.verification import evaluate_closure_evidence

        organization_id = self._ensure_write(user, org_context)
        enrollment = await self._get_or_create_enrollment(organization_id)
        stages = await self._seed_execution_stages(enrollment)
        complete_stage = next((s for s in stages if s.stage_key == "COMPLETE"), None)
        if complete_stage and complete_stage.status == "COMPLETED":
            return {
                "closure_status": "ALREADY_CLOSED",
                "complete_advanced": False,
                "enrollment_outcome": complete_stage.outcome,
                "operation_count": enrollment.operation_count,
                "blockers": [],
            }

        ops = list((await self.session.execute(
            select(PilotLiveOperation).where(
                PilotLiveOperation.organization_id == organization_id,
            ).order_by(PilotLiveOperation.created_at.asc())
        )).scalars().all())
        if len(ops) != 1:
            return {
                "closure_status": "BLOCKED",
                "complete_advanced": False,
                "verification_status": "INSUFFICIENT_EVIDENCE",
                "blockers": [f"operation_count={len(ops)} (expected 1)"],
                "operation_count": enrollment.operation_count,
            }
        op = ops[0]
        if op.status != "SUCCEEDED" or op.verification_status != "VERIFIED":
            return {
                "closure_status": "BLOCKED",
                "complete_advanced": False,
                "verification_status": "INSUFFICIENT_EVIDENCE",
                "blockers": [
                    f"operation_status={op.status}",
                    f"verification_status={op.verification_status}",
                ],
                "operation_count": enrollment.operation_count,
            }

        verify_stage = next((s for s in stages if s.stage_key == "VERIFY"), None)
        if not verify_stage or verify_stage.status != "COMPLETED":
            return {
                "closure_status": "BLOCKED",
                "complete_advanced": False,
                "verification_status": "INSUFFICIENT_EVIDENCE",
                "blockers": ["VERIFY stage not completed"],
                "operation_count": enrollment.operation_count,
            }

        target_replicas = int((op.params or {}).get("replicas", 2))
        closure_check = evaluate_closure_evidence(
            kubernetes_evidence=kubernetes_evidence,
            prometheus_evidence=prometheus_evidence,
            integration_evidence=integration_evidence,
            target_replicas=target_replicas,
        )
        if not closure_check["closure_ready"]:
            await self.audit.log(
                action="pilot.closure_blocked",
                resource_type="pilot_enrollment",
                resource_id=enrollment.id,
                user_id=user.id,
                organization_id=organization_id,
                details={"blockers": closure_check["blockers"]},
            )
            return {
                "closure_status": "BLOCKED",
                "complete_advanced": False,
                "verification_status": "INSUFFICIENT_EVIDENCE",
                "blockers": closure_check["blockers"],
                "operation_count": enrollment.operation_count,
                "operation_id": op.id,
            }

        outcome = "INTERNAL_NON_PRODUCTION_LIVE_PILOT_VERIFIED"
        evidence = {
            "operation_id": op.id,
            "verification_status": op.verification_status,
            "kubernetes_evidence": kubernetes_evidence,
            "prometheus_evidence": prometheus_evidence,
            "events_evidence": events_evidence,
            "integration_evidence": integration_evidence,
            "closure_check": closure_check,
            "scope": "internal_non_production_only",
        }
        await self._complete_stage(
            enrollment, "COMPLETE", owner_id=user.id,
            evidence=evidence,
            outcome=outcome,
        )
        enrollment.status = "COMPLETED"
        await self.audit.log(
            action="pilot.internal_closure_completed",
            resource_type="pilot_enrollment",
            resource_id=enrollment.id,
            user_id=user.id,
            organization_id=organization_id,
            details={
                "outcome": outcome,
                "operation_id": op.id,
                "operation_count": enrollment.operation_count,
            },
        )
        return {
            "closure_status": "CLOSED",
            "complete_advanced": True,
            "verification_status": "VERIFIED",
            "enrollment_outcome": outcome,
            "execution_status": enrollment.execution_status,
            "operation_count": enrollment.operation_count,
            "operation_id": op.id,
            "blockers": [],
        }

    async def _snapshot_approval_package(
        self,
        organization_id: str,
        enrollment: PilotEnrollment,
        op: PilotLiveOperation,
        approval: PilotApproval,
        env_name: str,
    ) -> PilotApprovalPackage:
        from app.models.organization import Organization

        org = await self.session.get(Organization, organization_id)
        org_name = org.name if org else "Customer Organization"
        phash = approval.payload_hash
        rhash = rollback_plan_hash(approval.rollback_plan)
        pkg = build_approval_package(
            operation={
                "id": op.id,
                "organization_id": organization_id,
                "action": op.action,
                "template_id": op.template_id,
                "status": op.status,
                "resource_name": op.resource_name,
                "cluster_id": op.cluster_id,
                "correlation_id": op.correlation_id,
                "payload_hash": phash,
                "params": op.params or {},
                "before_state": op.before_state or {},
                "rollback_plan": op.rollback_plan,
                "preflight": op.preflight or {},
            },
            approval={
                "id": approval.id,
                "status": approval.status,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                "approver_name": approval.approver_name,
                "approver_email": approval.approver_email,
                "operation_summary": approval.operation_summary,
                "rollback_plan": approval.rollback_plan,
                "payload_hash": phash,
                "target_environment": env_name,
            },
            enrollment={
                "id": enrollment.id,
                "kill_switch": enrollment.kill_switch,
                "operation_count": enrollment.operation_count,
                "operation_limit": enrollment.operation_limit,
            },
            baseline=enrollment.baseline or {},
            integration=None,
            preflight=op.preflight or {},
            organization_name=org_name,
        )
        row = PilotApprovalPackage(
            organization_id=organization_id,
            operation_id=op.id,
            approval_id=approval.id,
            payload_hash=phash,
            rollback_plan_hash=rhash,
            package=pkg,
            environment_id=op.environment_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def _check_approval_integration_readiness(
        self,
        op: PilotLiveOperation,
        approval: PilotApproval,
        organization_id: str,
    ) -> None:
        from app.pilot.launch_readiness import integration_freshness_ok
        from app.repositories.integration_readiness import IntRegistryRepo

        registry = IntRegistryRepo(self.session)
        rows = await registry.list_for_org(organization_id)
        k8s = None
        for row in rows:
            if row.provider_type == "KUBERNETES":
                if op.cluster_id and row.resource_id == op.cluster_id:
                    k8s = row
                    break
                k8s = k8s or row
        if not k8s:
            approval.status = "INVALIDATED"
            record_pilot_approval_event("invalidated")
            raise ValidationError("Approval invalidated — Kubernetes integration unavailable")
        stale = not integration_freshness_ok(k8s.last_validated_at)
        degraded = k8s.lifecycle_state in ("FAILED", "REAUTH_REQUIRED", "EXPIRED") or k8s.reauth_required
        if stale or degraded or k8s.lifecycle_state not in ("CONNECTED", "DEGRADED"):
            approval.status = "INVALIDATED"
            record_pilot_approval_event("invalidated")
            await emit_event(
                self.session, DomainEventType.PILOT_BLOCKED,
                organization_id=organization_id,
                payload={"reason": "approval_integration_stale", "approval_id": approval.id},
            )
            raise ValidationError("Approval invalidated — integration readiness changed")

        rhash = rollback_plan_hash(approval.rollback_plan)
        if (approval.rollback_plan or "") != (op.rollback_plan or ""):
            approval.status = "INVALIDATED"
            record_pilot_approval_event("invalidated")
            raise ValidationError("Approval invalidated — rollback plan changed")
        _ = rhash
