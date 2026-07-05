"""Sprint 41C — Real approved remediation execution.

Executes an *approved* remediation action against real customer infrastructure
using the customer's own encrypted credential (Sprint 35A/35D) and the existing
deployment providers (Sprint 36B Kubernetes rollback, Azure Container Apps, AWS
ECS, VM/SSH). No new execution engines: this orchestrates the existing providers.

Guarantees:
  * Execution requires an APPROVED action bound to known target infrastructure.
  * The customer credential is decrypted transiently, used in-process, and never
    logged, persisted, or returned. ``SECRET_USED`` is audited via the secret
    manager. Azure/AWS use the customer service principal/keys only — never the
    platform's.
  * Blocking SDK calls run off the event loop with a hard timeout.
  * Lifecycle is audited: ``remediation_execution_started / completed / failed``.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.security.secrets.service import SecretManagerService

logger = get_logger(__name__)


class RemediationExecutionError(Exception):
    """Customer-safe execution failure (never carries secrets/driver text)."""


# --------------------------------------------------------------------------- #
# Provider factories — overridable in tests (no live infra needed).
# --------------------------------------------------------------------------- #
def _k8s_provider():
    from app.deployment.kubernetes_provider import KubernetesDeploymentProvider

    return KubernetesDeploymentProvider()


def _azure_provider():
    from app.deployment.azure_container_apps import AzureContainerAppsProvider

    return AzureContainerAppsProvider()


def _aws_provider():
    from app.deployment.aws_ecs_provider import AWSEcsRemediationProvider

    return AWSEcsRemediationProvider()


def _vm_provider():
    from app.deployment.vm_provider import VMDeploymentProvider

    return VMDeploymentProvider()


PROVIDER_FACTORIES = {
    "KUBERNETES": _k8s_provider,
    "AZURE": _azure_provider,
    "AWS": _aws_provider,
    "VM": _vm_provider,
}


def _get_provider(name: str):
    factory = PROVIDER_FACTORIES.get(name)
    if factory is None:
        raise RemediationExecutionError(f"No remediation provider for {name}")
    return factory()


def _tc(action) -> dict:
    return action.target_config or {}


# --------------------------------------------------------------------------- #
# Per-(provider, action_type) dispatch. Each returns (result_str, metadata).
# --------------------------------------------------------------------------- #
def _k8s_rollback(action, target):
    dep = _tc(action).get("deployment_name") or action.application
    return _get_provider("KUBERNETES").remediation_rollback(
        namespace=action.namespace,
        deployment_name=dep,
        deployment_target=target,
        previous_revision=_tc(action).get("previous_revision"),
        ingress_url=_tc(action).get("ingress_url"),
    )


def _k8s_restart(action, target):
    dep = _tc(action).get("deployment_name") or action.application
    return _get_provider("KUBERNETES").restart(
        namespace=action.namespace, deployment_name=dep, deployment_target=target
    )


def _k8s_scale(action, target):
    dep = _tc(action).get("deployment_name") or action.application
    replicas = int(_tc(action).get("replicas") or 0)
    return _get_provider("KUBERNETES").scale(
        namespace=action.namespace,
        deployment_name=dep,
        replicas=replicas,
        deployment_target=target,
    )


def _azure_rollback(action, target):
    return _get_provider("AZURE").remediation_rollback_revision(
        container_app_name=action.application,
        deployment_target=target,
        previous_revision=_tc(action).get("previous_revision"),
    )


def _azure_restart(action, target):
    return _get_provider("AZURE").remediation_restart(
        container_app_name=action.application, deployment_target=target
    )


def _aws_target(action, target) -> dict:
    return {
        **target,
        "cluster": _tc(action).get("cluster") or action.namespace,
        "service": _tc(action).get("service") or action.application,
    }


def _aws_rollback(action, target):
    return _get_provider("AWS").rollback(deployment_target=_aws_target(action, target))


def _aws_restart(action, target):
    return _get_provider("AWS").restart(deployment_target=_aws_target(action, target))


def _vm_restart_stack(action, target):
    return _get_provider("VM").restart_stack(deployment_target=target)


def _vm_restart_service(action, target):
    svc = _tc(action).get("service_name") or action.application
    return _get_provider("VM").restart_service(service_name=svc, deployment_target=target)


DISPATCH = {
    ("KUBERNETES", "ROLLBACK_DEPLOYMENT"): _k8s_rollback,
    ("KUBERNETES", "RESTART_DEPLOYMENT"): _k8s_restart,
    ("KUBERNETES", "SCALE_DEPLOYMENT"): _k8s_scale,
    ("AZURE", "ROLLBACK_REVISION"): _azure_rollback,
    ("AZURE", "RESTART_CONTAINER_APP"): _azure_restart,
    ("AWS", "ROLLBACK_ECS"): _aws_rollback,
    ("AWS", "RESTART_ECS"): _aws_restart,
    ("VM", "RESTART_COMPOSE_STACK"): _vm_restart_stack,
    ("VM", "RESTART_SERVICE"): _vm_restart_service,
}


def is_supported(provider: str, action_type: str) -> bool:
    return (provider, action_type) in DISPATCH


class RemediationExecutor:
    """Resolves the customer credential and runs the bound provider operation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.secret_manager = SecretManagerService(session)
        self.audit_repo = AuditLogRepository(session)

    @property
    def _timeout(self) -> float:
        return float(getattr(settings, "DEPLOYMENT_TIMEOUT_SECONDS", 120)) + 30.0

    async def execute(
        self, action, *, user: User, org_context: OrgContext
    ) -> tuple[str, dict]:
        key = (action.provider, action.action_type)
        if key not in DISPATCH:
            raise RemediationExecutionError(
                f"Action {action.action_type} is not supported for {action.provider}."
            )
        if not action.credential_id:
            raise RemediationExecutionError(
                "Action is not bound to a target credential and cannot execute."
            )

        await self.audit_repo.log(
            action="remediation_execution_started",
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=user.id,
            details={"action_type": action.action_type, "provider": action.provider},
        )

        try:
            credential, secret = await self.secret_manager.resolve_secret(
                action.credential_id,
                user=user,
                org_context=org_context,
                reason=f"remediation:{action.action_type}",
                audit=True,
            )
            if credential.provider != action.provider:
                raise RemediationExecutionError(
                    "Bound credential provider does not match the action provider."
                )

            target = {**_tc(action), **secret}
            fn = DISPATCH[key]
            # Blocking SDK calls run off the loop with a hard timeout.
            result, rollback_metadata = await asyncio.wait_for(
                asyncio.to_thread(fn, action, target), timeout=self._timeout
            )
        except RemediationExecutionError:
            await self._audit_failed(action, user)
            raise
        except TimeoutError:
            await self._audit_failed(action, user, reason="timeout")
            raise RemediationExecutionError(
                "The remediation action timed out before completing."
            )
        except Exception as exc:  # noqa: BLE001 — never leak driver/secret text
            logger.error(
                "remediation_execution_error",
                action_type=action.action_type,
                provider=action.provider,
                error=type(exc).__name__,
            )
            await self._audit_failed(action, user)
            raise RemediationExecutionError(
                "The remediation action could not be completed against the target."
            )

        await self.audit_repo.log(
            action="remediation_execution_completed",
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=user.id,
            details={"action_type": action.action_type, "provider": action.provider},
        )
        return result, (rollback_metadata or {})

    async def _audit_failed(self, action, user: User, *, reason: str | None = None) -> None:
        details = {"action_type": action.action_type, "provider": action.provider}
        if reason:
            details["reason"] = reason
        await self.audit_repo.log(
            action="remediation_execution_failed",
            resource_type="incident_remediation_action",
            resource_id=action.id,
            user_id=user.id,
            details=details,
            status="failure",
        )
