"""Platform template definitions for environment factory."""

from __future__ import annotations

from app.platform_engineering.types import PlatformTemplateKind


def template_spec(kind: PlatformTemplateKind | str) -> dict:
    """Return the full platform template specification."""
    kind = PlatformTemplateKind(kind) if isinstance(kind, str) else kind
    base = {
        "networking": {"vpc": True, "subnets": 3, "nat_gateway": True},
        "iam": {"cluster_admin_role": True, "node_role": True},
        "storage": {"default_storage_class": "gp3"},
        "ingress": {"controller": "nginx", "tls": True},
        "observability": {"metrics": True, "logs": True, "traces": False},
        "security": {"pod_security": "restricted", "network_policies": True},
        "policies": {"opa": True, "admission_control": True},
        "namespaces": ["default", "platform", "monitoring"],
        "default_applications": [],
    }
    overlays = {
        PlatformTemplateKind.AKS: {
            "distribution": "AKS", "cloud": "AZURE",
            "default_applications": ["cert-manager", "external-dns"],
        },
        PlatformTemplateKind.EKS: {
            "distribution": "EKS", "cloud": "AWS",
            "default_applications": ["aws-load-balancer-controller", "cluster-autoscaler"],
        },
        PlatformTemplateKind.GKE: {
            "distribution": "GKE", "cloud": "GCP",
            "default_applications": ["gke-ingress", "config-connector"],
        },
        PlatformTemplateKind.K3S: {
            "distribution": "K3S", "cloud": "ANY",
            "networking": {"vpc": False, "subnets": 1},
            "default_applications": ["traefik"],
        },
        PlatformTemplateKind.OPENSHIFT: {
            "distribution": "OPENSHIFT", "cloud": "ANY",
            "security": {"pod_security": "openshift", "scc": True},
        },
        PlatformTemplateKind.DEV_ENV: {
            "tier": "DEVELOPMENT", "requires_approval": False,
            "default_applications": ["sample-api"],
        },
        PlatformTemplateKind.QA_ENV: {"tier": "QA", "requires_approval": False},
        PlatformTemplateKind.STAGING_ENV: {"tier": "STAGING", "requires_approval": True},
        PlatformTemplateKind.PRODUCTION_ENV: {
            "tier": "PRODUCTION", "requires_approval": True,
            "observability": {"metrics": True, "logs": True, "traces": True},
        },
    }
    spec = {**base, **overlays.get(kind, {})}
    spec["kind"] = kind.value
    return spec


def golden_template_spec(kind: str) -> dict:
    """Reusable company-standard application templates."""
    specs = {
        "MICROSERVICE": {
            "ci_cd": {"pipeline": "github-actions", "stages": ["build", "test", "deploy"]},
            "gitops": {"engine": "argocd", "sync_policy": "automated"},
            "monitoring": {"slo": True, "alerts": True},
            "policies": {"network_policy": True, "resource_quota": True},
            "secrets": {"backend": "vault", "rotation_days": 90},
            "rbac": {"service_account": True, "least_privilege": True},
        },
        "BACKEND_API": {
            "ci_cd": {"pipeline": "github-actions"},
            "gitops": {"engine": "argocd"},
            "monitoring": {"slo": True, "latency_p99": "500ms"},
            "ingress": {"path": "/api", "tls": True},
        },
        "FRONTEND": {
            "ci_cd": {"pipeline": "github-actions"},
            "gitops": {"engine": "argocd"},
            "ingress": {"cdn": True, "tls": True},
        },
        "WORKER": {"ci_cd": {"pipeline": "github-actions"}, "scaling": {"hpa": False, "keda": True}},
        "CRON": {"ci_cd": {"pipeline": "github-actions"}, "schedule": "0 * * * *"},
        "AI_SERVICE": {
            "ci_cd": {"pipeline": "github-actions"},
            "gpu": {"enabled": True},
            "monitoring": {"token_usage": True},
        },
        "BATCH_JOB": {"ci_cd": {"pipeline": "github-actions"}, "ttl_seconds": 3600},
    }
    return {"kind": kind, **specs.get(kind, specs["MICROSERVICE"])}
