"""Provider validators for customer integration onboarding (Sprint 67A)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.integration_readiness.evidence import redact_text
from app.services.integration_verification import VStatus, verify_provider

# Read-only K8s permissions required for onboarding
K8S_REQUIRED_READ = (
    ("apps", "deployments", "get"),
    ("apps", "deployments", "list"),
    ("apps", "deployments", "watch"),
    ("", "pods", "get"),
    ("", "pods", "list"),
    ("", "pods", "watch"),
    ("", "events", "get"),
    ("", "events", "list"),
    ("", "events", "watch"),
)

K8S_OPTIONAL_SCALE = (
    ("apps", "deployments/scale", "get"),
    ("apps", "deployments/scale", "patch"),
    ("apps", "deployments/scale", "update"),
)

K8S_PROHIBITED = (
    ("", "secrets", "get"),
    ("", "pods", "create"),
    ("", "pods/exec", "create"),
    ("", "pods/portforward", "create"),
    ("", "nodes", "get"),
    ("apps", "deployments", "delete"),
    ("apps", "deployments", "create"),
    ("rbac.authorization.k8s.io", "clusterroles", "get"),
    ("rbac.authorization.k8s.io", "clusterrolebindings", "get"),
)


def _ssar_check(auth_api, namespace: str, group: str, resource: str, verb: str) -> bool:
    from kubernetes import client

    body = client.V1SelfSubjectAccessReview(
        spec=client.V1SelfSubjectAccessReviewSpec(
            resource_attributes=client.V1ResourceAttributes(
                namespace=namespace if group not in ("rbac.authorization.k8s.io",) or resource.startswith("cluster") else None,
                verb=verb,
                group=group or None,
                resource=resource,
            ),
        ),
    )
    try:
        result = auth_api.create_self_subject_access_review(body)
        return bool(result.status and result.status.allowed)
    except Exception:
        return False


def _k8s_validate_sync(secret: dict, namespace: str) -> dict[str, Any]:
    import yaml
    from kubernetes import client, config
    from kubernetes.client.exceptions import ApiException

    raw = secret.get("kubeconfig")
    if not raw:
        return {
            "ok": False,
            "status": "FAILED",
            "provider_mode": "unavailable",
            "errors": ["kubeconfig is required"],
            "read_checks": [],
            "prohibited_granted": [],
            "rbac_gaps": ["kubeconfig_missing"],
            "inventory": {},
            "capabilities": {},
        }

    cfg = yaml.safe_load(raw)
    loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
    configuration = client.Configuration()
    loader.load_and_set(configuration)
    api_client = client.ApiClient(configuration)
    auth_api = client.AuthorizationV1Api(api_client)
    core = client.CoreV1Api(api_client)
    apps = client.AppsV1Api(api_client)

    read_checks: list[dict] = []
    rbac_gaps: list[str] = []
    for group, resource, verb in K8S_REQUIRED_READ:
        allowed = _ssar_check(auth_api, namespace, group, resource, verb)
        key = f"{group or 'core'}/{resource}:{verb}"
        read_checks.append({"permission": key, "allowed": allowed})
        if not allowed:
            rbac_gaps.append(key)

    scale_checks: list[dict] = []
    for group, resource, verb in K8S_OPTIONAL_SCALE:
        allowed = _ssar_check(auth_api, namespace, group, resource, verb)
        key = f"{group}/{resource}:{verb}"
        scale_checks.append({"permission": key, "allowed": allowed})

    prohibited_granted: list[str] = []
    for group, resource, verb in K8S_PROHIBITED:
        if _ssar_check(auth_api, namespace, group, resource, verb):
            prohibited_granted.append(f"{group or 'core'}/{resource}:{verb}")

    inventory: dict[str, Any] = {"namespace": namespace, "deployments": [], "pods": []}
    try:
        ns_list = core.list_namespace(limit=100)
        names = [i.metadata.name for i in ns_list.items]
        if namespace not in names:
            rbac_gaps.append("namespace_not_visible")
    except ApiException:
        pass

    try:
        for dep in apps.list_namespaced_deployment(namespace, limit=20).items:
            inventory["deployments"].append({
                "name": dep.metadata.name,
                "replicas": dep.spec.replicas if dep.spec else 0,
            })
    except ApiException:
        pass

    try:
        for pod in core.list_namespaced_pod(namespace, limit=50).items:
            inventory["pods"].append({
                "name": pod.metadata.name,
                "phase": pod.status.phase if pod.status else "Unknown",
            })
    except ApiException:
        pass

    has_scale = all(c["allowed"] for c in scale_checks)
    capabilities = {
        "read": not rbac_gaps,
        "kubernetes.workloads.read": not rbac_gaps,
        "kubernetes.workloads.write": has_scale,
        "kubernetes.workloads.scale": has_scale,
    }

    ok = not rbac_gaps and not prohibited_granted
    status = "VALIDATED" if ok else "FAILED"
    if prohibited_granted:
        status = "FAILED"

    return {
        "ok": ok,
        "status": status,
        "provider_mode": "live" if ok else "unavailable",
        "read_checks": read_checks,
        "scale_checks": scale_checks,
        "prohibited_granted": prohibited_granted,
        "rbac_gaps": rbac_gaps,
        "inventory": inventory,
        "capabilities": capabilities,
        "errors": [] if ok else ["RBAC validation failed"],
        "evidence_refs": {
            "namespace": namespace,
            "deployment_count": len(inventory.get("deployments", [])),
            "pod_count": len(inventory.get("pods", [])),
        },
    }


async def validate_kubernetes(secret: dict, *, namespace: str) -> dict[str, Any]:
    return await asyncio.to_thread(_k8s_validate_sync, secret, namespace)


async def validate_source_control(
    provider: str,
    secret: dict,
    *,
    repository: str,
    api_base_url: str | None = None,
) -> dict[str, Any]:
    probe_secret = dict(secret)
    if api_base_url:
        probe_secret["base_url"] = api_base_url.rstrip("/")

    key = "GITHUB" if provider in ("GITHUB", "GITHUB_ENTERPRISE", "GITEA") else provider
    if provider == "GITEA":
        key = "GITHUB"  # Gitea-compatible API

    result = await verify_provider(key, probe_secret)
    rd = result.to_dict()

    capabilities: dict[str, bool] = {"read": result.ok, "repository_metadata": result.ok}
    missing: list[str] = []
    insufficient: list[str] = []

    if result.ok and repository:
        # Repository scope check via API
        base = (probe_secret.get("base_url") or "https://api.github.com").rstrip("/")
        token = probe_secret.get("token", "")
        is_gitea = provider == "GITEA" or "gitea" in base.lower()
        auth_scheme = "token" if is_gitea else "Bearer"
        headers = {
            "Authorization": f"{auth_scheme} {token}",
            "Accept": "application/vnd.github+json" if not is_gitea else "application/json",
        }
        from app.services.integration_verification import _http_request

        try:
            owner, name = repository.split("/", 1)
            repo_resp = await _http_request(
                "GET", f"{base}/repos/{owner}/{name}", headers=headers,
            )
            repo_status = repo_resp.get("_status", 0)
            capabilities["repository_access"] = repo_status == 200
            if repo_status != 200:
                missing.append("repository_access")
        except Exception:
            capabilities["repository_access"] = False
            missing.append("repository_access")

        # Workflow history — optional
        try:
            wf_resp = await _http_request(
                "GET", f"{base}/repos/{owner}/{name}/actions/runs?per_page=1", headers=headers,
            )
            wf_status = wf_resp.get("_status", 0)
            if wf_status in (200, 201):
                capabilities["workflow_history"] = True
            elif wf_status in (403, 404):
                capabilities["workflow_history"] = False
                insufficient.append("workflow_history_unavailable")
            else:
                capabilities["workflow_history"] = False
                insufficient.append("workflow_history_unavailable")
        except Exception:
            capabilities["workflow_history"] = False
            insufficient.append("workflow_history_unavailable")

    ok = result.ok and capabilities.get("repository_access", False)
    verdict = "VALIDATED" if ok else "FAILED"
    if ok and insufficient:
        verdict = "VALIDATED"  # repo read works; workflow is INSUFFICIENT_EVIDENCE at readiness layer

    return {
        "ok": ok,
        "status": verdict,
        "provider_mode": "live" if ok and result.connection_status == VStatus.CONNECTED else "unavailable",
        "connection_status": result.connection_status,
        "capabilities": capabilities,
        "missing_capabilities": missing,
        "insufficient_evidence": insufficient,
        "provider_identity": rd.get("provider_identity") or {},
        "errors": [redact_text(e) for e in (rd.get("errors") or [])],
        "warnings": rd.get("warnings") or [],
        "evidence_refs": {
            "repository": repository,
            "identity_fields": list((rd.get("provider_identity") or {}).keys()),
        },
    }


async def validate_prometheus(secret: dict, *, scope: dict | None = None) -> dict[str, Any]:
    from app.pilot.assessment_collectors import collect_prometheus_evidence

    endpoint = (secret.get("endpoint") or secret.get("url") or "").strip()
    if not endpoint:
        return {
            "ok": False,
            "status": "FAILED",
            "provider_mode": "unavailable",
            "errors": ["Prometheus endpoint is required"],
            "capabilities": {},
            "evidence_refs": {},
        }

    ns = (scope or {}).get("label_value") or (scope or {}).get("namespace_label_value") or "default"
    evidence = await collect_prometheus_evidence(secret, namespace=ns)

    if evidence.get("prometheus_error") or evidence.get("error"):
        return {
            "ok": False,
            "status": "FAILED",
            "provider_mode": "unavailable",
            "errors": [redact_text(str(evidence.get("prometheus_error") or evidence.get("error")))],
            "capabilities": {"query_metrics": False},
            "evidence_refs": {"endpoint_host": endpoint.split("://")[-1].split("/")[0][:80]},
        }

    gaps = evidence.get("gaps") or []
    has_targets = bool(evidence.get("targets"))
    capabilities = {
        "query_metrics": evidence.get("source_mode") == "live",
        "read": evidence.get("source_mode") == "live",
    }
    insufficient = list(gaps)
    if not has_targets:
        insufficient.append("targets_unavailable")

    ok = capabilities["query_metrics"]
    return {
        "ok": ok,
        "status": "VALIDATED" if ok else "FAILED",
        "provider_mode": "live" if ok else "unavailable",
        "capabilities": capabilities,
        "missing_capabilities": gaps,
        "insufficient_evidence": insufficient,
        "errors": [],
        "warnings": gaps,
        "evidence_refs": {
            "endpoint_host": endpoint.split("://")[-1].split("/")[0][:80],
            "targets_up": (evidence.get("targets") or {}).get("up"),
            "namespace_label": ns,
        },
        "buildinfo": evidence.get("buildinfo"),
    }
