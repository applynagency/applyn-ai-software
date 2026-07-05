"""Live Argo CD GitOps provider — lists applications via Argo CD REST API."""

from __future__ import annotations

from app.delivery.gitops.engines import GitOpsApplication
from app.delivery.pipelines.ci_http import bearer_header, get_json, post_json


def list_applications(secret: dict) -> list[GitOpsApplication]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return []
    data = get_json(f"{endpoint}/api/v1/applications", headers=bearer_header(token))
    items = data.get("items") if isinstance(data, dict) else []
    apps: list[GitOpsApplication] = []
    for app in items or []:
        if not isinstance(app, dict):
            continue
        meta = app.get("metadata") or {}
        spec = app.get("spec") or {}
        status = app.get("status") or {}
        sync_info = status.get("sync") or {}
        health_info = status.get("health") or {}
        history_raw = status.get("history") or []
        history = [
            {"id": h.get("id"), "revision": h.get("revision")}
            for h in history_raw[:5]
            if isinstance(h, dict)
        ]
        sync_status = sync_info.get("status") or "Unknown"
        apps.append(GitOpsApplication(
            engine="ArgoCD",
            name=meta.get("name") or "",
            namespace=meta.get("namespace") or "default",
            project=spec.get("project") or "default",
            sync_status=sync_status,
            health=health_info.get("status") or "Unknown",
            revision=sync_info.get("revision") or "",
            auto_sync=bool((spec.get("syncPolicy") or {}).get("automated")),
            drift=sync_status == "OutOfSync",
            history=history,
        ))
    return apps


def sync_application(secret: dict, app_name: str, *, revision: str | None = None, prune: bool = False) -> dict:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token or not app_name:
        return {"app": app_name, "status": "failed", "simulated": True, "reason": "missing_credentials_or_app"}
    body: dict = {"prune": prune}
    if revision:
        body["revision"] = revision
    try:
        data = post_json(
            f"{endpoint}/api/v1/applications/{app_name}/sync",
            body,
            headers=bearer_header(token),
        )
    except RuntimeError as exc:
        return {"app": app_name, "engine": "ArgoCD", "status": "failed", "simulated": False, "error": str(exc)[:200]}
    return {
        "app": app_name,
        "engine": "ArgoCD",
        "status": "sync_triggered",
        "revision": revision or (data.get("metadata") or {}).get("resourceVersion"),
        "simulated": False,
        "response": {"phase": (data.get("status") or {}).get("operationState", {}).get("phase")},
    }


def rollback_application(secret: dict, app_name: str, revision_id: int) -> dict:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token or not app_name:
        return {"app": app_name, "status": "failed", "simulated": True, "reason": "missing_credentials_or_app"}
    try:
        post_json(
            f"{endpoint}/api/v1/applications/{app_name}/rollback",
            {"id": int(revision_id)},
            headers=bearer_header(token),
        )
    except RuntimeError as exc:
        return {"app": app_name, "engine": "ArgoCD", "status": "failed", "simulated": False, "error": str(exc)[:200]}
    return {
        "app": app_name,
        "engine": "ArgoCD",
        "status": "rollback_initiated",
        "revision": revision_id,
        "simulated": False,
    }


def application_diff(secret: dict, app_name: str) -> dict:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token or not app_name:
        return {"app": app_name, "diff": "unavailable", "simulated": True, "resources_changed": 0}
    try:
        data = get_json(
            f"{endpoint}/api/v1/applications/{app_name}/managed-resources",
            headers=bearer_header(token),
        )
    except RuntimeError as exc:
        return {"app": app_name, "diff": str(exc)[:200], "simulated": False, "resources_changed": 0, "error": True}
    items = (data.get("items") or []) if isinstance(data, dict) else []
    return {
        "app": app_name,
        "engine": "ArgoCD",
        "diff": f"{len(items)} managed resource(s)",
        "resources_changed": len(items),
        "simulated": False,
    }
