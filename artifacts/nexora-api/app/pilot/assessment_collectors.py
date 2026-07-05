"""Read-only pilot assessment collectors (Sprint 66D).

Gathers live evidence from Kubernetes, GitHub/Gitea, and Prometheus without
mutations. All outputs are redacted and secret-safe.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.integration_readiness.evidence import redact_text
from app.services.integration_verification import _http_request


@dataclass
class AssessmentFinding:
    finding_id: str
    title: str
    description: str
    source: str
    source_mode: str
    confidence: str
    risk: str
    evidence: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "source_mode": self.source_mode,
            "confidence": self.confidence,
            "risk": self.risk,
            "evidence": self.evidence,
            "gaps": self.gaps,
            "recommendation": self.recommendation,
        }


def _gh_base(secret: dict) -> str:
    return (secret.get("base_url") or "https://api.github.com").rstrip("/")


def _gh_headers(secret: dict) -> dict:
    return {
        "Authorization": f"Bearer {secret['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def collect_kubernetes_evidence(secret: dict, *, namespace: str) -> dict[str, Any]:
    """Read-only Kubernetes inventory for a pilot namespace."""

    def _run() -> dict[str, Any]:
        import yaml
        from kubernetes import client, config
        from kubernetes.client.exceptions import ApiException

        raw = secret.get("kubeconfig")
        if not raw:
            return {"error": "kubeconfig_missing", "source_mode": "unavailable"}

        cfg = yaml.safe_load(raw)
        loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
        configuration = client.Configuration()
        loader.load_and_set(configuration)
        api_client = client.ApiClient(configuration)

        current = cfg.get("current-context")
        cluster = ""
        for ctx in cfg.get("contexts", []):
            if ctx.get("name") == current:
                cluster = ctx.get("context", {}).get("cluster", "")

        core = client.CoreV1Api(api_client)
        apps = client.AppsV1Api(api_client)
        networking = client.NetworkingV1Api(api_client)

        version = None
        try:
            version = client.VersionApi(api_client).get_code().git_version
        except ApiException:
            pass

        namespaces: list[str] = []
        try:
            ns_list = core.list_namespace(limit=50)
            namespaces = [i.metadata.name for i in ns_list.items[:20]]
        except ApiException as exc:
            return {"error": "namespaces_unreadable", "status": exc.status, "source_mode": "live"}

        ns_exists = namespace in namespaces
        deployments: list[dict] = []
        pods: list[dict] = []
        services: list[dict] = []
        events: list[dict] = []
        network_policies: list[dict] = []

        if ns_exists:
            try:
                for dep in apps.list_namespaced_deployment(namespace, limit=50).items:
                    ready = 0
                    desired = dep.spec.replicas or 0
                    if dep.status and dep.status.ready_replicas:
                        ready = dep.status.ready_replicas
                    deployments.append({
                        "name": dep.metadata.name,
                        "replicas_desired": desired,
                        "replicas_ready": ready,
                        "available": bool(dep.status and dep.status.available_replicas),
                    })
            except ApiException:
                pass

            try:
                for pod in core.list_namespaced_pod(namespace, limit=100).items:
                    restarts = 0
                    ready_count = 0
                    total_containers = 0
                    requests: dict[str, dict] = {}
                    limits: dict[str, dict] = {}
                    if pod.status and pod.status.container_statuses:
                        total_containers = len(pod.status.container_statuses)
                        for cs in pod.status.container_statuses:
                            restarts += cs.restart_count or 0
                            if cs.ready:
                                ready_count += 1
                    if pod.spec and pod.spec.containers:
                        for c in pod.spec.containers:
                            if c.resources:
                                if c.resources.requests:
                                    requests[c.name] = dict(c.resources.requests)
                                if c.resources.limits:
                                    limits[c.name] = dict(c.resources.limits)
                    pods.append({
                        "name": pod.metadata.name,
                        "phase": pod.status.phase if pod.status else "Unknown",
                        "ready": f"{ready_count}/{total_containers}",
                        "restart_count": restarts,
                        "resource_requests": requests or None,
                        "resource_limits": limits or None,
                    })
            except ApiException:
                pass

            try:
                for svc in core.list_namespaced_service(namespace, limit=50).items:
                    services.append({
                        "name": svc.metadata.name,
                        "type": svc.spec.type,
                        "cluster_ip": svc.spec.cluster_ip,
                        "ports": [p.port for p in (svc.spec.ports or [])],
                    })
            except ApiException:
                pass

            try:
                for ev in core.list_namespaced_event(namespace, limit=30).items:
                    events.append({
                        "type": ev.type,
                        "reason": ev.reason,
                        "object": f"{ev.involved_object.kind}/{ev.involved_object.name}" if ev.involved_object else "",
                        "message": redact_text((ev.message or "")[:200]),
                        "count": ev.count,
                        "last_timestamp": ev.last_timestamp.isoformat() if ev.last_timestamp else None,
                    })
            except ApiException:
                pass

            try:
                for np in networking.list_namespaced_network_policy(namespace, limit=20).items:
                    network_policies.append({"name": np.metadata.name})
            except ApiException:
                pass

        return {
            "source_mode": "live",
            "cluster": cluster or "kubernetes",
            "api_server": configuration.host,
            "version": version,
            "namespaces_observed": namespaces,
            "namespace": namespace,
            "namespace_exists": ns_exists,
            "deployments": deployments,
            "pods": pods,
            "services": services,
            "events": events[:15],
            "network_policies": network_policies,
        }

    return await asyncio.to_thread(_run)


async def collect_github_evidence(secret: dict, *, repository: str) -> dict[str, Any]:
    """Read-only repository metadata, commits, and workflow visibility."""
    base = _gh_base(secret)
    headers = _gh_headers(secret)
    owner, _, repo = repository.partition("/")
    if not owner or not repo:
        return {"error": "invalid_repository", "source_mode": "unavailable"}

    out: dict[str, Any] = {"source_mode": "live", "repository": repository}
    gaps: list[str] = []

    try:
        meta = await _http_request("GET", f"{base}/repos/{owner}/{repo}", headers=headers)
        m = meta["_json"]
        out["metadata"] = {
            "full_name": m.get("full_name"),
            "default_branch": m.get("default_branch"),
            "visibility": m.get("visibility") or ("private" if m.get("private") else "public"),
            "open_issues": m.get("open_issues_count"),
            "pushed_at": m.get("pushed_at"),
            "size": m.get("size"),
        }
    except Exception:  # noqa: BLE001
        return {"error": "repository_unreadable", "source_mode": "live", "repository": repository}

    commits: list[dict] = []
    try:
        data = await _http_request(
            "GET", f"{base}/repos/{owner}/{repo}/commits", headers=headers, params={"per_page": 5},
        )
        for c in data["_json"][:5]:
            if not isinstance(c, dict):
                continue
            commit = c.get("commit") or {}
            commits.append({
                "sha": (c.get("sha") or "")[:12],
                "message": redact_text((commit.get("message") or "")[:120]),
                "author": (commit.get("author") or {}).get("name"),
                "date": (commit.get("author") or {}).get("date"),
            })
        out["recent_commits"] = commits
    except Exception:  # noqa: BLE001
        gaps.append("recent_commits_unavailable")
        out["recent_commits"] = []

    workflows: list[dict] = []
    runs: list[dict] = []
    try:
        wf = await _http_request("GET", f"{base}/repos/{owner}/{repo}/actions/workflows", headers=headers)
        for w in (wf["_json"].get("workflows") or [])[:10]:
            if isinstance(w, dict):
                workflows.append({"id": w.get("id"), "name": w.get("name"), "state": w.get("state")})
        out["workflows"] = workflows
    except Exception:  # noqa: BLE001
        gaps.append("workflows_unavailable")
        out["workflows"] = []

    try:
        run_data = await _http_request(
            "GET", f"{base}/repos/{owner}/{repo}/actions/runs", headers=headers, params={"per_page": 5},
        )
        for r in (run_data["_json"].get("workflow_runs") or [])[:5]:
            if isinstance(r, dict):
                runs.append({
                    "name": r.get("name"),
                    "status": r.get("status"),
                    "conclusion": r.get("conclusion"),
                    "event": r.get("event"),
                    "created_at": r.get("created_at"),
                })
        out["workflow_runs"] = runs
    except Exception:  # noqa: BLE001
        gaps.append("workflow_runs_unavailable")
        out["workflow_runs"] = []

    try:
        prot = await _http_request("GET", f"{base}/repos/{owner}/{repo}/branches/{out['metadata']['default_branch']}/protection", headers=headers)
        out["branch_protection"] = {"protected": True, "summary": "readable"}
        _ = prot
    except Exception:  # noqa: BLE001
        gaps.append("branch_protection_not_readable")
        out["branch_protection"] = None

    try:
        rel = await _http_request("GET", f"{base}/repos/{owner}/{repo}/releases", headers=headers, params={"per_page": 3})
        out["releases"] = [
            {"tag": r.get("tag_name"), "name": r.get("name"), "published_at": r.get("published_at")}
            for r in rel["_json"][:3] if isinstance(r, dict)
        ]
    except Exception:  # noqa: BLE001
        gaps.append("releases_unavailable")
        out["releases"] = []

    out["gaps"] = gaps
    return out


async def collect_prometheus_evidence(secret: dict, *, namespace: str) -> dict[str, Any]:
    """Read-only Prometheus health, targets, and safe sample queries."""
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}"} if secret.get("token") else None
    out: dict[str, Any] = {"source_mode": "live", "endpoint": endpoint, "queries": []}
    gaps: list[str] = []

    try:
        build = await _http_request("GET", f"{endpoint}/api/v1/status/buildinfo", headers=headers)
        out["buildinfo"] = build["_json"].get("data") or {}
    except Exception:  # noqa: BLE001
        return {"error": "prometheus_unreachable", "source_mode": "live", "endpoint": endpoint}

    try:
        targets = await _http_request("GET", f"{endpoint}/api/v1/targets", headers=headers)
        active = (targets["_json"].get("data") or {}).get("activeTargets") or []
        out["targets"] = {
            "total": len(active),
            "up": sum(1 for t in active if (t.get("health") == "up")),
            "down": sum(1 for t in active if (t.get("health") != "up")),
            "jobs": sorted({t.get("labels", {}).get("job", "") for t in active if isinstance(t, dict)})[:10],
        }
    except Exception:  # noqa: BLE001
        gaps.append("targets_unavailable")
        out["targets"] = None

    safe_queries = [
        ("up", "up"),
        ("prometheus_ready", "prometheus_ready"),
        (
            "kube_pod_container_status_restarts_total",
            f'kube_pod_container_status_restarts_total{{namespace="{namespace}"}}',
        ),
        (
            "kube_deployment_status_replicas_available",
            f'kube_deployment_status_replicas_available{{namespace="{namespace}"}}',
        ),
    ]
    for name, expr in safe_queries:
        try:
            res = await _http_request(
                "GET", f"{endpoint}/api/v1/query", headers=headers, params={"query": expr},
            )
            result = (res["_json"].get("data") or {}).get("result") or []
            sample = []
            for row in result[:5]:
                metric = row.get("metric") or {}
                sample.append({
                    "metric": {k: v for k, v in metric.items() if k in ("namespace", "pod", "deployment", "job", "__name__")},
                    "value": row.get("value"),
                })
            out["queries"].append({
                "name": name,
                "expression": expr,
                "series_count": len(result),
                "sample": sample,
            })
        except Exception:  # noqa: BLE001
            out["queries"].append({"name": name, "expression": expr, "error": "query_failed"})
            if name.startswith("kube_"):
                gaps.append(f"{name}_insufficient_evidence")

    if not any(q.get("series_count", 0) > 0 for q in out["queries"] if q["name"].startswith("kube_")):
        gaps.append("namespace_workload_metrics_unavailable")

    out["gaps"] = gaps
    return out


def build_findings(
    *,
    kubernetes: dict | None,
    github: dict | None,
    prometheus: dict | None,
) -> list[AssessmentFinding]:
    findings: list[AssessmentFinding] = []

    if kubernetes and not kubernetes.get("error"):
        ns = kubernetes.get("namespace", "")
        if kubernetes.get("namespace_exists"):
            pods = kubernetes.get("pods") or []
            deps = kubernetes.get("deployments") or []
            restarts = sum(p.get("restart_count", 0) for p in pods)
            not_ready = [p["name"] for p in pods if p.get("phase") not in ("Running", "Succeeded") and p.get("phase")]
            risk = "LOW"
            if restarts > 0:
                risk = "MEDIUM"
            if not_ready:
                risk = "HIGH"
            findings.append(AssessmentFinding(
                finding_id="k8s-namespace-inventory",
                title=f"Namespace '{ns}' inventory captured",
                description=(
                    f"Observed {len(deps)} deployment(s), {len(pods)} pod(s), "
                    f"{len(kubernetes.get('services') or [])} service(s) in live cluster."
                ),
                source="KUBERNETES",
                source_mode=kubernetes.get("source_mode", "live"),
                confidence="HIGH",
                risk="INFO" if not pods and not deps else risk,
                evidence=[{
                    "type": "kubernetes_inventory",
                    "cluster": kubernetes.get("cluster"),
                    "namespace": ns,
                    "deployments": deps,
                    "pods": pods,
                    "events": kubernetes.get("events") or [],
                }],
            ))
            if restarts > 0:
                findings.append(AssessmentFinding(
                    finding_id="k8s-pod-restarts",
                    title="Pod restart activity detected",
                    description=f"Total container restart count in namespace: {restarts}.",
                    source="KUBERNETES",
                    source_mode="live",
                    confidence="HIGH",
                    risk="MEDIUM",
                    evidence=[{"type": "pod_restarts", "total_restarts": restarts, "pods": pods}],
                    recommendation="Review recent namespace events before any future rollout.",
                ))
            if not pods and not deps:
                findings.append(AssessmentFinding(
                    finding_id="k8s-empty-namespace",
                    title="Pilot namespace has no workloads",
                    description="Namespace exists but no deployments or pods were observed.",
                    source="KUBERNETES",
                    source_mode="live",
                    confidence="HIGH",
                    risk="INFO",
                    evidence=[{"type": "empty_namespace", "namespace": ns}],
                    recommendation="Deploy a non-production pilot workload to enable deeper health signals.",
                ))
        else:
            findings.append(AssessmentFinding(
                finding_id="k8s-namespace-missing",
                title="Pilot namespace not found",
                description=f"Namespace '{ns}' was not listed by the API.",
                source="KUBERNETES",
                source_mode="live",
                confidence="MEDIUM",
                risk="MEDIUM",
                evidence=[{"type": "namespace_missing", "namespace": ns}],
                gaps=["namespace_not_observed"],
            ))
    elif kubernetes:
        findings.append(AssessmentFinding(
            finding_id="k8s-collection-failed",
            title="Kubernetes evidence unavailable",
            description="Could not complete read-only Kubernetes collection.",
            source="KUBERNETES",
            source_mode=kubernetes.get("source_mode", "unavailable"),
            confidence="INSUFFICIENT_EVIDENCE",
            risk="MEDIUM",
            evidence=[{"error": kubernetes.get("error")}],
            gaps=["kubernetes_collection_failed"],
        ))

    if github and not github.get("error"):
        meta = github.get("metadata") or {}
        gaps = list(github.get("gaps") or [])
        findings.append(AssessmentFinding(
            finding_id="github-repo-metadata",
            title=f"Repository {github.get('repository')} metadata captured",
            description=f"Default branch: {meta.get('default_branch', 'unknown')}.",
            source="GITHUB",
            source_mode="live",
            confidence="HIGH" if meta else "INSUFFICIENT_EVIDENCE",
            risk="INFO",
            evidence=[{
                "type": "repository_metadata",
                "metadata": meta,
                "recent_commits": github.get("recent_commits") or [],
            }],
            gaps=gaps,
        ))
        runs = github.get("workflow_runs") or []
        if runs:
            failed = [r for r in runs if r.get("conclusion") not in (None, "success", "skipped")]
            findings.append(AssessmentFinding(
                finding_id="github-pipeline-runs",
                title="Recent workflow runs observed",
                description=f"Captured {len(runs)} recent run(s).",
                source="GITHUB",
                source_mode="live",
                confidence="HIGH",
                risk="MEDIUM" if failed else "INFO",
                evidence=[{"type": "workflow_runs", "runs": runs}],
            ))
        elif "workflow_runs_unavailable" in gaps:
            findings.append(AssessmentFinding(
                finding_id="github-pipelines-insufficient",
                title="Pipeline run history not available",
                description="Workflow definitions or runs could not be read with current token scope.",
                source="GITHUB",
                source_mode="live",
                confidence="INSUFFICIENT_EVIDENCE",
                risk="INFO",
                evidence=[{"workflows": github.get("workflows") or []}],
                gaps=["workflow_runs_unavailable"],
            ))
    elif github:
        findings.append(AssessmentFinding(
            finding_id="github-collection-failed",
            title="GitHub/Gitea evidence unavailable",
            description="Could not complete read-only repository collection.",
            source="GITHUB",
            source_mode=github.get("source_mode", "unavailable"),
            confidence="INSUFFICIENT_EVIDENCE",
            risk="MEDIUM",
            evidence=[{"error": github.get("error")}],
            gaps=["github_collection_failed"],
        ))

    if prometheus and not prometheus.get("error"):
        gaps = list(prometheus.get("gaps") or [])
        targets = prometheus.get("targets") or {}
        findings.append(AssessmentFinding(
            finding_id="prometheus-health",
            title="Prometheus endpoint healthy",
            description="Build info and target summary collected via read-only API.",
            source="PROMETHEUS",
            source_mode="live",
            confidence="HIGH",
            risk="INFO",
            evidence=[{
                "type": "prometheus_health",
                "buildinfo": prometheus.get("buildinfo"),
                "targets": targets,
                "queries": prometheus.get("queries") or [],
            }],
            gaps=gaps,
        ))
        if "namespace_workload_metrics_unavailable" in gaps:
            findings.append(AssessmentFinding(
                finding_id="prometheus-workload-metrics-gap",
                title="No workload metrics for pilot namespace",
                description="Prometheus did not return series for namespace-scoped kube-state metrics.",
                source="PROMETHEUS",
                source_mode="live",
                confidence="INSUFFICIENT_EVIDENCE",
                risk="INFO",
                evidence=[{"queries": prometheus.get("queries") or []}],
                gaps=["namespace_workload_metrics_unavailable"],
                recommendation="Configure scrape targets for the pilot namespace before SLO-style analysis.",
            ))
    elif prometheus:
        findings.append(AssessmentFinding(
            finding_id="prometheus-collection-failed",
            title="Prometheus evidence unavailable",
            description="Could not query Prometheus read-only API.",
            source="PROMETHEUS",
            source_mode=prometheus.get("source_mode", "unavailable"),
            confidence="INSUFFICIENT_EVIDENCE",
            risk="MEDIUM",
            evidence=[{"error": prometheus.get("error")}],
            gaps=["prometheus_collection_failed"],
        ))

    return findings


def build_baseline_snapshot(
    *,
    assessment_summary: dict,
    integration_health: list[dict],
    captured_at: str,
) -> dict[str, Any]:
    """Derive a timestamped baseline from assessment evidence."""
    k8s = assessment_summary.get("kubernetes") or {}
    gh = assessment_summary.get("github") or {}
    prom = assessment_summary.get("prometheus") or {}
    pods = k8s.get("pods") or []
    baseline = {
        "captured_at": captured_at,
        "workload": {
            "name": "pilot-demo",
            "namespace": (k8s.get("namespace") if k8s else None) or "nexora-pilot",
            "deployments": k8s.get("deployments") or [],
            "pods": k8s.get("pods") or [],
        },
        "deployment_readiness": [
            {"name": d.get("name"), "desired": d.get("replicas_desired"), "ready": d.get("replicas_ready")}
            for d in (k8s.get("deployments") or [])
        ],
        "pod_readiness": [
            {"name": p.get("name"), "phase": p.get("phase"), "ready": p.get("ready"), "restarts": p.get("restart_count")}
            for p in pods
        ],
        "total_restarts": sum(p.get("restart_count", 0) for p in pods),
        "recent_events": (k8s.get("events") or [])[:10],
        "pipeline_status": gh.get("workflow_runs") or [],
        "repository_default_branch": (gh.get("metadata") or {}).get("default_branch"),
        "prometheus_targets": prom.get("targets"),
        "prometheus_queries": prom.get("queries") or [],
        "integration_health": integration_health,
    }
    return baseline
