"""Helm release management — repositories, upgrades, rollbacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HelmRepository:
    name: str
    url: str
    index_age: str | None = None


@dataclass
class HelmRelease:
    name: str
    namespace: str
    chart: str
    version: str
    status: str
    revision: int
    values: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)


def list_repositories() -> list[HelmRepository]:
    return [
        HelmRepository("bitnami", "https://charts.bitnami.com/bitnami"),
        HelmRepository("prometheus-community", "https://prometheus-community.github.io/helm-charts"),
        HelmRepository("ingress-nginx", "https://kubernetes.github.io/ingress-nginx"),
    ]


def list_installed_releases(cluster_name: str) -> list[HelmRelease]:
    """Deterministic catalog when helm CLI is not wired; upgradeable via operations API."""
    return [
        HelmRelease("ingress-nginx", "ingress", "ingress-nginx", "4.10.0", "deployed", 3,
                    values={"controller.replicaCount": 2}),
        HelmRelease("prometheus", "monitoring", "kube-prometheus-stack", "55.0.0", "deployed", 2),
        HelmRelease("checkout", "production", "checkout", "1.4.2", "deployed", 5,
                    values={"replicaCount": 3},
                    history=[{"revision": 4, "status": "superseded"}, {"revision": 5, "status": "deployed"}]),
    ]


def diff_values(current: dict, proposed: dict) -> dict:
    added = {k: v for k, v in proposed.items() if k not in current}
    removed = {k: v for k, v in current.items() if k not in proposed}
    changed = {k: {"from": current[k], "to": proposed[k]}
               for k in proposed if k in current and current[k] != proposed[k]}
    return {"added": added, "removed": removed, "changed": changed}


async def helm_dry_run(action: str, release: str, namespace: str, values: dict | None = None) -> dict:
    return {
        "action": action, "release": release, "namespace": namespace,
        "dry_run": True, "would_apply": values or {},
        "manifest_preview": f"# simulated manifest for {release}",
    }
