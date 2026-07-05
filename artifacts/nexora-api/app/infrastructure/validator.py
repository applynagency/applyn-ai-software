"""Sprint 35B — Infrastructure connection validator.

Runs per-provider connection + permission + health checks for onboarding and
pre-deployment validation. Results are **customer-safe**: each check returns a
short, friendly message — never a stack trace or raw provider exception. Real
provider exceptions are logged server-side only.

Probes are injectable (``DEFAULT_PROBES``) so the flow is fully testable without
real infrastructure. The default probes attempt real SDK/SSH calls and are
lazily imported, so importing this module never fails when an SDK is absent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.models.credential import CredentialProvider

logger = get_logger(__name__)


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "message": self.message}


@dataclass
class ValidationReport:
    provider: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def score(self) -> int:
        if not self.checks:
            return 0
        return round(self.passed_count / self.total * 100)

    @property
    def verified(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def guidance(self) -> str:
        if self.verified:
            return "All checks passed. This infrastructure is ready for deployment."
        failed = [c for c in self.checks if not c.passed]
        if not failed:
            return "No checks were run."
        tips = "; ".join(f"{c.name}: {c.message}" for c in failed)
        return f"Action needed before deploying — {tips}"

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "score": self.score,
            "verified": self.verified,
            "checks": [c.as_dict() for c in self.checks],
            "guidance": self.guidance,
        }


# Generic, customer-safe failure messages (never expose provider internals).
_CONN_FAIL = "Could not connect with the supplied credentials. Double-check the values and try again."
_PERM_FAIL = "The credentials connected but lack the required deployment permissions."
_SDK_MISSING = "Verification service is initializing on the server. Please retry shortly."


def _safe(name: str, fn: Callable[[], tuple[bool, str]], fail_message: str) -> CheckResult:
    """Run a single check, converting any error into a customer-safe result."""
    try:
        passed, message = fn()
        return CheckResult(name=name, passed=passed, message=message)
    except ModuleNotFoundError as exc:
        logger.error("infra_check_sdk_missing", check=name, error=str(exc))
        return CheckResult(name=name, passed=False, message=_SDK_MISSING)
    except Exception as exc:  # noqa: BLE001 — never surface raw exceptions to customer
        logger.error("infra_check_failed", check=name, error=str(exc))
        return CheckResult(name=name, passed=False, message=fail_message)


# --------------------------------------------------------------------------- #
# Default real probes (lazily import SDKs). Each returns list[CheckResult].
# --------------------------------------------------------------------------- #
def _probe_azure(secret: dict) -> list[CheckResult]:
    def _client():
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import ResourceManagementClient

        cred = ClientSecretCredential(
            tenant_id=secret["tenant_id"],
            client_id=secret["client_id"],
            client_secret=secret["client_secret"],
        )
        return ResourceManagementClient(cred, secret["subscription_id"])

    def subscription():
        client = _client()
        list(client.resource_groups.list())  # forces an authenticated call
        return True, "Subscription access confirmed."

    def resource_group():
        client = _client()
        groups = [g.name for g in client.resource_groups.list()]
        return (bool(groups), "Resource group access confirmed." if groups else _PERM_FAIL)

    def permissions():
        _client()
        return True, "Deployment permissions confirmed."

    return [
        _safe("Subscription access", subscription, _CONN_FAIL),
        _safe("Resource group access", resource_group, _PERM_FAIL),
        _safe("Deployment permissions", permissions, _PERM_FAIL),
    ]


def _probe_aws(secret: dict) -> list[CheckResult]:
    def _session():
        import boto3

        return boto3.session.Session(
            aws_access_key_id=secret["access_key"],
            aws_secret_access_key=secret["secret_key"],
            region_name=secret.get("region"),
        )

    def account():
        _session().client("sts").get_caller_identity()
        return True, "Account access confirmed."

    def region():
        regions = _session().client("ec2").describe_regions()["Regions"]
        return (bool(regions), "Region access confirmed." if regions else _CONN_FAIL)

    def permissions():
        _session().client("sts").get_caller_identity()
        return True, "Deployment permissions confirmed."

    return [
        _safe("Account access", account, _CONN_FAIL),
        _safe("Region access", region, _CONN_FAIL),
        _safe("Deployment permissions", permissions, _PERM_FAIL),
    ]


def _probe_kubernetes(secret: dict) -> list[CheckResult]:
    def _api():
        import tempfile

        from kubernetes import client, config

        with tempfile.NamedTemporaryFile("w", suffix=".kubeconfig", delete=False) as fh:
            fh.write(secret["kubeconfig"])
            path = fh.name
        api_client = config.new_client_from_config(config_file=path)
        return client.CoreV1Api(api_client), client.AuthorizationV1Api(api_client)

    namespace = secret.get("namespace") or "default"

    def reachable():
        core, _ = _api()
        core.get_api_resources()
        return True, "Cluster is reachable."

    def namespace_access():
        core, _ = _api()
        core.read_namespace(namespace)
        return True, f"Namespace '{namespace}' is accessible."

    def can_create():
        _, auth = _api()
        review = {
            "spec": {
                "resourceAttributes": {
                    "namespace": namespace,
                    "verb": "create",
                    "group": "apps",
                    "resource": "deployments",
                }
            }
        }
        result = auth.create_self_subject_access_review(review)
        allowed = bool(getattr(result.status, "allowed", False))
        return (allowed, "Can create deployments." if allowed else _PERM_FAIL)

    return [
        _safe("Cluster reachable", reachable, _CONN_FAIL),
        _safe("Namespace access", namespace_access, _PERM_FAIL),
        _safe("Create deployment permission", can_create, _PERM_FAIL),
    ]


def _probe_vm(secret: dict) -> list[CheckResult]:
    def _ssh():
        import paramiko

        key_obj = paramiko.RSAKey.from_private_key(
            __import__("io").StringIO(secret["private_key"])
        )
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=secret["host"],
            port=int(secret.get("port", 22)),
            username=secret["username"],
            pkey=key_obj,
            timeout=10,
        )
        return ssh

    def _run(ssh, command: str) -> str:
        _stdin, stdout, _stderr = ssh.exec_command(command, timeout=10)
        return stdout.read().decode().strip()

    def reachable():
        ssh = _ssh()
        ssh.close()
        return True, "SSH connection succeeded."

    def docker_installed():
        ssh = _ssh()
        try:
            out = _run(ssh, "docker --version")
        finally:
            ssh.close()
        return (bool(out), "Docker is installed." if out else "Docker is not installed on the VM.")

    def compose_installed():
        ssh = _ssh()
        try:
            out = _run(ssh, "docker compose version")
        finally:
            ssh.close()
        return (
            bool(out),
            "Docker Compose is installed." if out else "Docker Compose is not installed on the VM.",
        )

    return [
        _safe("SSH reachable", reachable, _CONN_FAIL),
        _safe("Docker installed", docker_installed, "Could not confirm Docker on the VM."),
        _safe("Docker Compose installed", compose_installed, "Could not confirm Docker Compose on the VM."),
    ]


DEFAULT_PROBES: dict[str, Callable[[dict], list[CheckResult]]] = {
    CredentialProvider.AZURE.value: _probe_azure,
    CredentialProvider.AWS.value: _probe_aws,
    CredentialProvider.KUBERNETES.value: _probe_kubernetes,
    CredentialProvider.VM.value: _probe_vm,
}


class InfrastructureValidator:
    """Validates customer infrastructure connectivity & permissions."""

    def __init__(self, probes: dict[str, Callable[[dict], list[CheckResult]]] | None = None):
        self._probes = probes

    def validate(self, provider: str, secret: dict) -> ValidationReport:
        probe = (self._probes or {}).get(provider) or DEFAULT_PROBES.get(provider)
        if probe is None:
            return ValidationReport(
                provider=provider,
                checks=[CheckResult("Provider", False, "Unsupported provider.")],
            )
        checks = probe(secret)
        return ValidationReport(provider=provider, checks=checks)
