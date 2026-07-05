"""GitOps engine abstraction for delivery platform."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GitOpsApplication:
    engine: str
    name: str
    namespace: str
    project: str
    sync_status: str
    health: str
    revision: str
    auto_sync: bool
    drift: bool
    history: list[dict]


def list_argocd_applications(cluster_name: str, secret: dict | None = None) -> list[GitOpsApplication]:
    if secret and secret.get("token") and secret.get("endpoint"):
        from app.delivery.gitops import argocd_live

        return argocd_live.list_applications(secret)
    return []


def list_flux_applications(cluster_name: str, secret: dict | None = None) -> list[GitOpsApplication]:
    if secret and secret.get("kubeconfig"):
        from app.delivery.gitops import flux_live

        return flux_live.list_applications(secret)
    return []


def gitops_diff(app_name: str, engine: str = "ArgoCD", secret: dict | None = None) -> dict:
    if engine == "Flux" and secret:
        from app.delivery.gitops import flux_live

        return flux_live.application_diff(secret, app_name)
    if engine == "ArgoCD" and secret:
        from app.delivery.gitops import argocd_live

        return argocd_live.application_diff(secret, app_name)
    return {
        "app": app_name, "engine": engine,
        "diff": "No differences (simulated)",
        "resources_changed": 0,
        "simulated": True,
    }


def gitops_sync(
    app_name: str,
    engine: str = "ArgoCD",
    secret: dict | None = None,
    *,
    revision: str | None = None,
    prune: bool = False,
) -> dict:
    if engine == "Flux" and secret:
        from app.delivery.gitops import flux_live

        return flux_live.sync_application(secret, app_name, revision=revision, prune=prune)
    if engine == "ArgoCD" and secret:
        from app.delivery.gitops import argocd_live

        return argocd_live.sync_application(secret, app_name, revision=revision, prune=prune)
    return {"app": app_name, "engine": engine, "status": "sync_triggered", "revision": "abc123", "simulated": True}


def gitops_rollback(app_name: str, revision: int, engine: str = "ArgoCD", secret: dict | None = None) -> dict:
    if engine == "ArgoCD" and secret:
        from app.delivery.gitops import argocd_live

        return argocd_live.rollback_application(secret, app_name, revision)
    return {"app": app_name, "engine": engine, "status": "rollback_initiated", "revision": revision, "simulated": True}
