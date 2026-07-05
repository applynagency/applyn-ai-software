"""Sprint 41B — Approval-Based Remediation Actions.

Converts Sprint 41A recommendations into *executable* remediation actions that
are gated behind mandatory human approval:

    Incident → Investigation → Recommendation → Approval → Safe Execution

Hard safety rules enforced here:
  * No autonomous remediation, no self-healing, no automatic execution.
  * An action stays ``PENDING_APPROVAL`` until a human explicitly approves it.
  * Execution is only ever attempted when ``status == APPROVED``.
  * An already-decided action cannot be re-approved/re-rejected (409 Conflict).
  * All lookups are organization-scoped (cross-org → 404).
  * Every lifecycle transition is audit-logged. No secrets are read/logged/stored.

Execution dispatches through the existing deployment-provider abstraction
(``app.deployment.deployer`` — Kubernetes rollback/restart, Azure revision
activation, VM compose restart, AWS ECS). When a live deployment target and
credential are not bound to the action, execution runs in a guarded mode that
performs no live infrastructure mutation and records a deterministic,
customer-safe result — consistent with the platform's "simulated when not
configured" philosophy. The provider seam is documented in ``_execute_action``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.core.logging import get_logger
from app.models.incident import (
    RemediationActionStatus,
    RemediationApprovalStatus,
)
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import (
    IncidentInvestigationRepository,
    IncidentRemediationActionRepository,
    IncidentRemediationApprovalRepository,
)
from app.schemas.incident import (
    RemediationActionListResponse,
    RemediationActionResponse,
    RemediationApprovalListResponse,
    RemediationApprovalResponse,
)
from app.services.remediation_execution import RemediationExecutor, is_supported
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Action generation — map an advisory recommendation to an executable action.
# (recommendation_type, title-keyword) -> (action_type, provider)
# Only a safe, explicit allow-list of actions is ever generated.
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(UTC)


def _version_from(text: str | None) -> str | None:
    if not text:
        return None
    for token in text.replace("(", " ").replace(")", " ").split():
        t = token.strip(".,")
        if t.startswith("v") and any(c.isdigit() for c in t):
            return t
    return None


def plan_actions(recommendations: list) -> list[dict]:
    """Pure mapping: advisory recommendations -> executable action specs.

    Returns a list of action-spec dicts (no DB). Only rollback/restart/scale
    recommendations become actions; investigative recommendations do not.
    """
    specs: list[dict] = []
    for rec in recommendations:
        rec_type = (_attr(rec, "recommendation_type") or "").lower()
        title = (_attr(rec, "title") or "")
        tl = title.lower()
        risk = _attr(rec, "risk_level") or "HIGH"
        rec_id = _attr(rec, "id")
        version = _version_from(title)

        action_type = provider = None
        if rec_type == "deployment" and "rollback" in tl:
            action_type, provider, risk = "ROLLBACK_DEPLOYMENT", "KUBERNETES", "HIGH"
        elif rec_type == "kubernetes" and ("restart" in tl or "pod" in tl):
            action_type, provider = "RESTART_DEPLOYMENT", "KUBERNETES"
        elif rec_type == "kubernetes" and ("scale" in tl or "replica" in tl):
            action_type, provider = "SCALE_DEPLOYMENT", "KUBERNETES"
        if not action_type:
            continue

        specs.append(
            {
                "recommendation_id": rec_id,
                "action_type": action_type,
                "provider": provider,
                "title": title,
                "description": _attr(rec, "description"),
                "risk_level": risk,
                "action_metadata": {"version": version} if version else {},
            }
        )
    return specs


def _attr(o, name):
    return o.get(name) if isinstance(o, dict) else getattr(o, name, None)


class RemediationActionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IncidentRemediationActionRepository(session)
        self.approval_repo = IncidentRemediationApprovalRepository(session)
        self.investigation_repo = IncidentInvestigationRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.executor = RemediationExecutor(session)

    # ------------------------------------------------------------- guards
    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    async def _get_action_or_404(self, action_id: str, organization_id: str):
        action = await self.repo.get_for_org(action_id, organization_id)
        if action is None:
            raise NexoraException("Remediation action not found.", status_code=404)
        return action

    @staticmethod
    def _is_executable(action) -> bool:
        """An action can only run once bound to known target infrastructure."""
        if not action.credential_id or not action.application:
            return False
        if action.provider == "KUBERNETES" and not action.namespace:
            return False
        return is_supported(action.provider, action.action_type)

    # ------------------------------------------------------------- binding
    async def bind(
        self,
        action_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        credential_id: str,
        environment: str | None = None,
        namespace: str | None = None,
        application: str | None = None,
        target_config: dict | None = None,
    ) -> RemediationActionResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        if action.status != RemediationActionStatus.PENDING_APPROVAL.value:
            raise NexoraException(
                f"Only a pending action can be bound (current status: {action.status}).",
                status_code=409,
            )
        # Validate the credential exists, is org-scoped, and matches the provider.
        credential = await self.executor.secret_manager.repo.get_for_org(
            credential_id, organization_id
        )
        if credential is None:
            raise NexoraException("Credential not found.", status_code=404)
        if credential.provider != action.provider:
            raise NexoraException(
                f"Credential provider {credential.provider} does not match action "
                f"provider {action.provider}.",
                status_code=422,
            )
        action = await self.repo.update(
            action,
            credential_id=credential_id,
            environment=environment,
            namespace=namespace,
            application=application,
            target_config=target_config or {},
        )
        await self.audit_repo.log(
            action="remediation_action_bound",
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=current_user.id,
            details={
                "provider": action.provider,
                "environment": environment,
                "namespace": namespace,
                "application": application,
                "credential_id": credential_id,
            },
        )
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    # ------------------------------------------------------------- generation
    async def generate_for_investigation(
        self,
        *,
        investigation,
        organization_id: str,
        recommendations: list,
        user_id: str | None,
        context: dict | None = None,
    ) -> list:
        """Create PENDING_APPROVAL actions from a set of recommendations.

        Called by the incident engine after recommendations are persisted. Each
        generated action requires explicit human approval before any execution.
        """
        specs = plan_actions(recommendations)
        created = []
        for spec in specs:
            action = await self.repo.create(
                organization_id=organization_id,
                investigation_id=investigation.id,
                recommendation_id=spec["recommendation_id"],
                action_type=spec["action_type"],
                provider=spec["provider"],
                title=spec["title"][:255],
                description=spec["description"],
                risk_level=spec["risk_level"],
                status=RemediationActionStatus.PENDING_APPROVAL.value,
                action_metadata=spec["action_metadata"],
            )
            created.append(action)
            await self.audit_repo.log(
                action="remediation_action_created",
                resource_type="incident_remediation_action",
                resource_id=action.id,
                user_id=user_id,
                details={
                    "investigation_id": investigation.id,
                    "action_type": action.action_type,
                    "provider": action.provider,
                    "risk_level": action.risk_level,
                },
            )
        if created:
            await self.auto_bind_pending(
                actions=created,
                organization_id=organization_id,
                investigation=investigation,
                context=context,
                user_id=user_id,
            )
        return created

    # ------------------------------------------------------------- auto-bind
    @staticmethod
    def _target_hints_from_context(context: dict | None, investigation) -> dict[str, str]:
        """Derive bind targets from investigation context (alert service, job, etc.)."""
        hints: dict[str, str] = {}
        ctx = context or {}
        env = (ctx.get("environment") or "production").strip() or "production"
        hints["environment"] = env[:64]
        service = (
            ctx.get("service")
            or ctx.get("application")
            or ctx.get("job")
            or ctx.get("pipeline")
            or ""
        )
        if not service and investigation and getattr(investigation, "title", None):
            title = investigation.title
            if title.startswith("[") and "]" in title:
                title = title.split("]", 1)[1].strip()
            service = title.split("—", 1)[0].strip() if "—" in title else title
        app = (str(service).strip() or "api").lower().replace(" ", "-")[:64]
        hints["application"] = app
        ns = (ctx.get("namespace") or env).strip() or env
        hints["namespace"] = ns[:64]
        return hints

    async def auto_bind_pending(
        self,
        *,
        actions: list,
        organization_id: str,
        investigation=None,
        context: dict | None = None,
        user_id: str | None = None,
    ) -> int:
        """Bind pending actions when a matching org credential + target can be inferred."""
        if not actions:
            return 0
        hints = self._target_hints_from_context(context, investigation)
        creds, _ = await self.executor.secret_manager.repo.list_for_org(
            organization_id, limit=100
        )
        active = [c for c in creds if getattr(c, "is_active", True)]
        bound = 0
        for action in actions:
            if action.status != RemediationActionStatus.PENDING_APPROVAL.value:
                continue
            if self._is_executable(action):
                continue
            matching = [c for c in active if c.provider == action.provider]
            if not matching:
                continue
            credential = matching[0]
            action = await self.repo.update(
                action,
                credential_id=credential.id,
                environment=hints["environment"],
                namespace=hints["namespace"] if action.provider == "KUBERNETES" else None,
                application=hints["application"],
            )
            if not self._is_executable(action):
                continue
            bound += 1
            await self.audit_repo.log(
                action="remediation_action_auto_bound",
                resource_type="incident_remediation_action",
                resource_id=action.id,
                user_id=user_id,
                details={
                    "provider": action.provider,
                    "credential_id": credential.id,
                    "environment": hints["environment"],
                    "namespace": hints.get("namespace"),
                    "application": hints["application"],
                },
            )
        return bound

    async def auto_bind_action(
        self,
        action_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        context: dict | None = None,
    ) -> RemediationActionResponse:
        """Attempt to auto-bind a single pending action (idempotent)."""
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        if action.status != RemediationActionStatus.PENDING_APPROVAL.value:
            raise NexoraException(
                f"Only a pending action can be auto-bound (current status: {action.status}).",
                status_code=409,
            )
        if self._is_executable(action):
            return RemediationActionResponse.model_validate(action)
        investigation = await self.investigation_repo.get_for_org(
            action.investigation_id, organization_id
        )
        await self.auto_bind_pending(
            actions=[action],
            organization_id=organization_id,
            investigation=investigation,
            context=context,
            user_id=current_user.id,
        )
        action = await self._get_action_or_404(action_id, organization_id)
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    # ------------------------------------------------------------- reads
    async def list_for_incident(
        self, investigation_id: str, current_user: User, org_context: OrgContext
    ) -> RemediationActionListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        investigation = await self.investigation_repo.get_for_org(
            investigation_id, organization_id
        )
        if investigation is None:
            raise NexoraException("Investigation not found.", status_code=404)
        actions = await self.repo.list_for_investigation(investigation.id, organization_id)
        return RemediationActionListResponse(
            investigation_id=investigation.id,
            actions=[RemediationActionResponse.model_validate(a) for a in actions],
        )

    async def get_action(
        self, action_id: str, current_user: User, org_context: OrgContext
    ) -> RemediationActionResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        return RemediationActionResponse.model_validate(action)

    async def list_approvals(
        self, action_id: str, current_user: User, org_context: OrgContext
    ) -> RemediationApprovalListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        approvals = await self.approval_repo.list_for_action(action.id, organization_id)
        return RemediationApprovalListResponse(
            action_id=action.id,
            approvals=[RemediationApprovalResponse.model_validate(a) for a in approvals],
        )

    # ------------------------------------------------------------- approve
    async def approve(
        self,
        action_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        comments: str | None = None,
    ) -> RemediationActionResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)

        # Double-approval protection: only a pending action can be approved.
        if action.status != RemediationActionStatus.PENDING_APPROVAL.value:
            raise NexoraException(
                f"Action is not pending approval (current status: {action.status}).",
                status_code=409,
            )

        # Sprint 41C — an action cannot be approved/executed until it is bound to
        # known target infrastructure (credential + target). Status is unchanged.
        if not self._is_executable(action):
            raise NexoraException(
                "Action must be bound to a credential and target infrastructure "
                "before it can be approved.",
                status_code=422,
            )

        action = await self.repo.update(
            action,
            status=RemediationActionStatus.APPROVED.value,
            approved_by=current_user.id,
            approved_at=_now(),
        )
        await self.approval_repo.create(
            organization_id=organization_id,
            action_id=action.id,
            approver_user_id=current_user.id,
            status=RemediationApprovalStatus.APPROVED.value,
            comments=comments,
        )
        await self.audit_repo.log(
            action="remediation_action_approved",
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=current_user.id,
            details={"action_type": action.action_type, "provider": action.provider},
        )

        # Execution is only ever reached after an explicit approval.
        action = await self._execute(action, current_user, org_context)
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    # ------------------------------------------------------------- reject
    async def reject(
        self,
        action_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        comments: str | None = None,
    ) -> RemediationActionResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)

        if action.status != RemediationActionStatus.PENDING_APPROVAL.value:
            raise NexoraException(
                f"Action is not pending approval (current status: {action.status}).",
                status_code=409,
            )

        action = await self.repo.update(
            action, status=RemediationActionStatus.REJECTED.value
        )
        await self.approval_repo.create(
            organization_id=organization_id,
            action_id=action.id,
            approver_user_id=current_user.id,
            status=RemediationApprovalStatus.REJECTED.value,
            comments=comments,
        )
        await self.audit_repo.log(
            action="remediation_action_rejected",
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=current_user.id,
            details={"action_type": action.action_type, "provider": action.provider},
        )
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    # ------------------------------------------------------------- pause / resume
    async def pause(
        self, action_id: str, current_user: User, org_context: OrgContext,
        *, comments: str | None = None,
    ) -> RemediationActionResponse:
        """Hold a pending action so it cannot be approved until resumed."""
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        if action.status != RemediationActionStatus.PENDING_APPROVAL.value:
            raise NexoraException(
                f"Only a pending action can be paused (current status: {action.status}).",
                status_code=409)
        action = await self.repo.update(action, status=RemediationActionStatus.PAUSED.value)
        await self._audit(action, current_user, "remediation_action_paused", comments)
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    async def resume(
        self, action_id: str, current_user: User, org_context: OrgContext,
        *, comments: str | None = None,
    ) -> RemediationActionResponse:
        """Release a paused action back to pending approval."""
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        if action.status != RemediationActionStatus.PAUSED.value:
            raise NexoraException(
                f"Only a paused action can be resumed (current status: {action.status}).",
                status_code=409)
        action = await self.repo.update(
            action, status=RemediationActionStatus.PENDING_APPROVAL.value)
        await self._audit(action, current_user, "remediation_action_resumed", comments)
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    # ------------------------------------------------------------- retry
    async def retry(
        self, action_id: str, current_user: User, org_context: OrgContext,
        *, comments: str | None = None,
    ) -> RemediationActionResponse:
        """Re-run a previously FAILED action (still bound + human-initiated)."""
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        if action.status != RemediationActionStatus.FAILED.value:
            raise NexoraException(
                f"Only a failed action can be retried (current status: {action.status}).",
                status_code=409)
        if not self._is_executable(action):
            raise NexoraException(
                "Action must be bound to a credential and target before retry.",
                status_code=422)
        action = await self.repo.update(
            action, status=RemediationActionStatus.APPROVED.value,
            approved_by=current_user.id, approved_at=_now(), error_message=None)
        await self._audit(action, current_user, "remediation_action_retried", comments)
        action = await self._execute(action, current_user, org_context)
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    # ------------------------------------------------------------- override
    async def override(
        self, action_id: str, current_user: User, org_context: OrgContext,
        *, comments: str | None = None,
    ) -> RemediationActionResponse:
        """Authoritatively approve + execute an action, overriding a prior
        reject/pause decision. Requires an explicit justification and still runs
        only against bound target infrastructure (no autonomous/unbound mutation).
        """
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)
        action = await self._get_action_or_404(action_id, organization_id)
        if not (comments or "").strip():
            raise NexoraException("An override requires a justification.", status_code=400)
        overridable = {
            RemediationActionStatus.PENDING_APPROVAL.value,
            RemediationActionStatus.PAUSED.value,
            RemediationActionStatus.REJECTED.value,
        }
        if action.status not in overridable:
            raise NexoraException(
                f"Action cannot be overridden (current status: {action.status}).",
                status_code=409)
        if not self._is_executable(action):
            raise NexoraException(
                "Action must be bound to a credential and target before it can be "
                "overridden.", status_code=422)
        action = await self.repo.update(
            action, status=RemediationActionStatus.APPROVED.value,
            approved_by=current_user.id, approved_at=_now())
        await self.approval_repo.create(
            organization_id=organization_id, action_id=action.id,
            approver_user_id=current_user.id,
            status=RemediationApprovalStatus.APPROVED.value,
            comments=f"OVERRIDE: {comments}")
        await self._audit(action, current_user, "remediation_action_overridden", comments)
        action = await self._execute(action, current_user, org_context)
        await self.session.commit()
        return RemediationActionResponse.model_validate(action)

    async def _audit(self, action, current_user: User, action_name: str, comments: str | None) -> None:
        await self.audit_repo.log(
            action=action_name,
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=current_user.id,
            details={"action_type": action.action_type, "provider": action.provider,
                     "comments": (comments or "")[:500]},
        )

    # ------------------------------------------------------------- execution
    async def _execute(self, action, current_user: User, org_context: OrgContext):
        """Run an APPROVED action against real infrastructure.

        Delegates to :class:`RemediationExecutor`, which resolves the customer
        credential and dispatches to the existing deployment providers. Never
        called for a non-approved action.
        """
        if action.status != RemediationActionStatus.APPROVED.value:
            raise NexoraException("Action must be approved before execution.", status_code=409)

        action = await self.repo.update(
            action, status=RemediationActionStatus.EXECUTING.value
        )
        await self.audit_repo.log(
            action="remediation_action_started",
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=current_user.id,
            details={"action_type": action.action_type, "provider": action.provider},
        )
        try:
            result, rollback_metadata = await self.executor.execute(
                action, user=current_user, org_context=org_context
            )
            merged_meta = {**(action.action_metadata or {}), "rollback_metadata": rollback_metadata}
            action = await self.repo.update(
                action,
                status=RemediationActionStatus.COMPLETED.value,
                executed_at=_now(),
                execution_result=result,
                error_message=None,
                action_metadata=merged_meta,
            )
            await self.audit_repo.log(
                action="remediation_action_completed",
                resource_type="incident_remediation_action",
                resource_id=action.id,
                user_id=current_user.id,
                details={"action_type": action.action_type, "provider": action.provider},
            )
        except Exception as exc:  # noqa: BLE001 - never leak internals to the client
            message = getattr(exc, "message", None) or str(exc)
            # RemediationExecutionError carries a customer-safe message; anything
            # else collapses to a generic one.
            if exc.__class__.__name__ != "RemediationExecutionError":
                message = "The remediation action could not be completed."
            action = await self.repo.update(
                action,
                status=RemediationActionStatus.FAILED.value,
                executed_at=_now(),
                error_message=message,
            )
            await self.audit_repo.log(
                action="remediation_action_failed",
                resource_type="incident_remediation_action",
                resource_id=action.id,
                user_id=current_user.id,
                details={"action_type": action.action_type, "provider": action.provider},
                status="failure",
            )
            logger.error("remediation_action_failed", error=type(exc).__name__)
        return action
