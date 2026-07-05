"""Live Flux CD GitOps provider — reads Kustomizations via Kubernetes API."""

from __future__ import annotations

from datetime import UTC, datetime

from app.delivery.gitops.engines import GitOpsApplication


def _api_from_kubeconfig(secret: dict):
    import yaml
    from kubernetes import client, config

    raw = secret.get("kubeconfig")
    if not raw:
        return None
    cfg = yaml.safe_load(raw)
    loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
    configuration = client.Configuration()
    loader.load_and_set(configuration)
    return client.CustomObjectsApi(client.ApiClient(configuration))


def _ready_condition(conditions: list) -> dict:
    for cond in conditions or []:
        if isinstance(cond, dict) and cond.get("type") == "Ready":
            return cond
    return {}


def _kustomization_to_app(item: dict) -> GitOpsApplication | None:
    if not isinstance(item, dict):
        return None
    meta = item.get("metadata") or {}
    spec = item.get("spec") or {}
    status = item.get("status") or {}
    ready = _ready_condition(status.get("conditions"))
    is_ready = ready.get("status") == "True"
    applied = status.get("lastAppliedRevision") or ""
    attempted = status.get("lastAttemptedRevision") or ""
    drift = bool(applied and attempted and applied != attempted) or not is_ready
    history = [{"id": 0, "revision": applied}] if applied else []
    return GitOpsApplication(
        engine="Flux",
        name=meta.get("name") or "",
        namespace=meta.get("namespace") or "default",
        project=spec.get("targetNamespace") or meta.get("namespace") or "default",
        sync_status="Synced" if is_ready and not drift else (ready.get("reason") or "NotReady"),
        health="Healthy" if is_ready else "Degraded",
        revision=applied,
        auto_sync=bool(spec.get("interval")),
        drift=drift,
        history=history,
    )


def list_applications(secret: dict) -> list[GitOpsApplication]:
    api = _api_from_kubeconfig(secret)
    if api is None:
        return []
    apps: list[GitOpsApplication] = []
    try:
        data = api.list_cluster_custom_object(
            group="kustomize.toolkit.fluxcd.io",
            version="v1",
            plural="kustomizations",
        )
        for item in (data.get("items") or []):
            app = _kustomization_to_app(item)
            if app and app.name:
                apps.append(app)
    except Exception:  # noqa: BLE001 - cluster may lack Flux CRDs
        pass
    if apps:
        return apps
    try:
        data = api.list_namespaced_custom_object(
            group="kustomize.toolkit.fluxcd.io",
            version="v1",
            namespace="flux-system",
            plural="kustomizations",
        )
        for item in (data.get("items") or []):
            app = _kustomization_to_app(item)
            if app and app.name:
                apps.append(app)
    except Exception:  # noqa: BLE001
        pass
    return apps


def sync_application(secret: dict, app_name: str, *, revision: str | None = None, prune: bool = False) -> dict:
    api = _api_from_kubeconfig(secret)
    if api is None or not app_name:
        return {"app": app_name, "status": "failed", "simulated": True, "reason": "missing_kubeconfig_or_app"}
    ts = datetime.now(UTC).isoformat()
    patch = {
        "metadata": {
            "annotations": {
                "reconcile.fluxcd.io/requestedAt": ts,
                "reconcile.fluxcd.io/forceAt": ts if prune else None,
            },
        },
    }
    patch["metadata"]["annotations"] = {k: v for k, v in patch["metadata"]["annotations"].items() if v}
    namespaces = ["flux-system", "default"]
    last_error = None
    for ns in namespaces:
        try:
            api.patch_namespaced_custom_object(
                group="kustomize.toolkit.fluxcd.io",
                version="v1",
                namespace=ns,
                plural="kustomizations",
                name=app_name,
                body=patch,
            )
            return {
                "app": app_name,
                "engine": "Flux",
                "status": "sync_triggered",
                "revision": revision,
                "simulated": False,
                "namespace": ns,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:200]
    return {
        "app": app_name,
        "engine": "Flux",
        "status": "failed",
        "simulated": False,
        "error": last_error or "kustomization not found",
    }


def application_diff(secret: dict, app_name: str) -> dict:
    api = _api_from_kubeconfig(secret)
    if api is None or not app_name:
        return {"app": app_name, "diff": "unavailable", "simulated": True, "resources_changed": 0}
    for ns in ("flux-system", "default"):
        try:
            item = api.get_namespaced_custom_object(
                group="kustomize.toolkit.fluxcd.io",
                version="v1",
                namespace=ns,
                plural="kustomizations",
                name=app_name,
            )
            status = item.get("status") or {}
            applied = status.get("lastAppliedRevision") or ""
            attempted = status.get("lastAttemptedRevision") or ""
            drift = applied != attempted if applied and attempted else False
            return {
                "app": app_name,
                "engine": "Flux",
                "diff": "Out of sync" if drift else "In sync",
                "resources_changed": 1 if drift else 0,
                "simulated": False,
                "revision": applied,
            }
        except Exception:  # noqa: BLE001
            continue
    return {"app": app_name, "diff": "kustomization not found", "simulated": False, "resources_changed": 0}
